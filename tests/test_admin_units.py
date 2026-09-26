"""admin/admin_units.py — /api/au1|au2|au3, /api/school_category."""
import pytest

from conftest import uniq


def _code(prefix):
    # Текст PK — seed-ийн 3/5 оронтой кодуудтай давхцахгүй
    return uniq(prefix)


@pytest.fixture
def au1(api):
    code = _code("A")
    r = api.post("/api/au1", json={"code": code, "name": "Тест аймаг"})
    assert r.status_code == 201, r.get_json()
    return code


@pytest.fixture
def au2(api, au1):
    code = _code("B")
    r = api.post("/api/au2", json={"au2_code": code, "au2_name": "Тест сум",
                                   "au1_code": au1})
    assert r.status_code == 201, r.get_json()
    return au1, code


# ---------------------------------------------------------------- au1
def test_au1_list_contains_seed(api):
    r = api.get("/api/au1")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list) and data
    assert any(x["code"] == "011" for x in data)
    assert data == sorted(data, key=lambda x: x["code"])


def test_au1_get(api):
    r = api.get("/api/au1/011")
    assert r.status_code == 200
    assert r.get_json()["code"] == "011"
    assert r.get_json()["name"]


def test_au1_get_404(api):
    r = api.get("/api/au1/NOPE999")
    assert r.status_code == 404
    assert "error" in r.get_json()


def test_au1_create_update_delete(api):
    code = _code("A")
    r = api.post("/api/au1", json={"code": code, "name": "Шинэ"})
    assert r.status_code == 201
    assert r.get_json() == {"code": code, "name": "Шинэ"}
    assert api.get(f"/api/au1/{code}").get_json()["name"] == "Шинэ"

    r = api.put(f"/api/au1/{code}", json={"name": "Засвар"})
    assert r.status_code == 200
    assert r.get_json() == {"code": code, "name": "Засвар"}
    r = api.patch(f"/api/au1/{code}", json={"name": "Засвар2"})
    assert r.status_code == 200
    assert api.get(f"/api/au1/{code}").get_json()["name"] == "Засвар2"

    r = api.delete(f"/api/au1/{code}")
    assert r.status_code == 200
    assert r.get_json() == {"deleted": code}
    assert api.get(f"/api/au1/{code}").status_code == 404


def test_au1_create_missing_field_400(api):
    assert api.post("/api/au1", json={"code": _code("A")}).status_code == 400
    assert api.post("/api/au1", json={}).status_code == 400
    assert api.post("/api/au1").status_code == 400


def test_au1_create_duplicate_409(api, au1):
    r = api.post("/api/au1", json={"code": au1, "name": "Дахин"})
    assert r.status_code == 409
    assert "error" in r.get_json()


def test_au1_update_400_404(api, au1):
    assert api.put(f"/api/au1/{au1}", json={}).status_code == 400
    assert api.put("/api/au1/NOPE999", json={"name": "x"}).status_code == 404
    assert api.patch("/api/au1/NOPE999", json={"name": "x"}).status_code == 404


def test_au1_delete_404(api):
    assert api.delete("/api/au1/NOPE999").status_code == 404


def test_au1_delete_cascades_to_au2_au3(api, au2):
    a1, a2 = au2
    a3 = _code("C")
    r = api.post("/api/au3", json={"au3_code": a3, "au3_name": "Баг",
                                   "au1_code": a1, "au2_code": a2})
    assert r.status_code == 201
    assert api.delete(f"/api/au1/{a1}").status_code == 200
    assert api.get(f"/api/au2/{a2}").status_code == 404
    assert api.get(f"/api/au3/{a3}").status_code == 404


# ---------------------------------------------------------------- au2
def test_au2_list_and_filter(api, au2):
    a1, a2 = au2
    all_ = api.get("/api/au2").get_json()
    assert any(x["au2_code"] == a2 for x in all_)
    r = api.get(f"/api/au2?au1_code={a1}")
    assert r.status_code == 200
    assert [x["au2_code"] for x in r.get_json()] == [a2]
    seeded = api.get("/api/au2?au1_code=011").get_json()
    assert seeded and all(x["au1_code"] == "011" for x in seeded)


def test_au2_get_and_404(api, au2):
    a1, a2 = au2
    r = api.get(f"/api/au2/{a2}")
    assert r.status_code == 200
    assert r.get_json() == {**r.get_json(), "au2_code": a2, "au1_code": a1,
                            "au2_name": "Тест сум"}
    assert api.get("/api/au2/NOPE999").status_code == 404


def test_au2_create_validation(api, au1):
    assert api.post("/api/au2", json={"au2_code": _code("B"),
                                      "au2_name": "x"}).status_code == 400
    r = api.post("/api/au2", json={"au2_code": _code("B"), "au2_name": "x",
                                   "au1_code": "NOPE999"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_au2_duplicate_409(api, au2):
    a1, a2 = au2
    r = api.post("/api/au2", json={"au2_code": a2, "au2_name": "x", "au1_code": a1})
    assert r.status_code == 409


def test_au2_update_put_patch_delete(api, au2):
    _, a2 = au2
    r = api.put(f"/api/au2/{a2}", json={"au2_name": "Шинэ нэр"})
    assert r.status_code == 200
    assert r.get_json() == {"au2_code": a2, "au2_name": "Шинэ нэр"}
    assert api.patch(f"/api/au2/{a2}", json={"au2_name": "П"}).status_code == 200
    assert api.get(f"/api/au2/{a2}").get_json()["au2_name"] == "П"
    assert api.put(f"/api/au2/{a2}", json={}).status_code == 400
    assert api.put("/api/au2/NOPE999", json={"au2_name": "x"}).status_code == 404
    r = api.delete(f"/api/au2/{a2}")
    assert r.status_code == 200 and r.get_json() == {"deleted": a2}
    assert api.delete(f"/api/au2/{a2}").status_code == 404


# ---------------------------------------------------------------- au3
def test_au3_crud_and_filters(api, au2):
    a1, a2 = au2
    a3 = _code("C")
    body = {"au3_code": a3, "au3_name": "Баг 1", "au1_code": a1, "au2_code": a2}
    r = api.post("/api/au3", json=body)
    assert r.status_code == 201 and r.get_json() == body

    assert [x["au3_code"] for x in api.get(f"/api/au3?au2_code={a2}").get_json()] == [a3]
    assert [x["au3_code"] for x in api.get(f"/api/au3?au1_code={a1}").get_json()] == [a3]
    assert any(x["au3_code"] == a3 for x in api.get("/api/au3").get_json())

    r = api.get(f"/api/au3/{a3}")
    assert r.status_code == 200 and r.get_json()["au3_name"] == "Баг 1"

    r = api.put(f"/api/au3/{a3}", json={"au3_name": "Баг 2"})
    assert r.status_code == 200
    assert r.get_json() == {"au3_code": a3, "au3_name": "Баг 2"}
    assert api.patch(f"/api/au3/{a3}", json={"au3_name": "Баг 3"}).status_code == 200
    assert api.get(f"/api/au3/{a3}").get_json()["au3_name"] == "Баг 3"

    assert api.post("/api/au3", json=body).status_code == 409
    r = api.delete(f"/api/au3/{a3}")
    assert r.status_code == 200 and r.get_json() == {"deleted": a3}
    assert api.get(f"/api/au3/{a3}").status_code == 404


def test_au3_errors(api, au2):
    a1, _ = au2
    assert api.post("/api/au3", json={"au3_code": _code("C"),
                                      "au3_name": "x"}).status_code == 400
    r = api.post("/api/au3", json={"au3_code": _code("C"), "au3_name": "x",
                                   "au1_code": a1, "au2_code": "NOPE999"})
    assert r.status_code == 400
    assert api.get("/api/au3/NOPE999").status_code == 404
    assert api.put("/api/au3/NOPE999", json={"au3_name": "x"}).status_code == 404
    assert api.put("/api/au3/NOPE999", json={}).status_code == 400
    assert api.delete("/api/au3/NOPE999").status_code == 404


# ---------------------------------------------------------------- school_category
def _free_cat_id(api):
    used = {c["id"] for c in api.get("/api/school_category").get_json()}
    for i in range(98, 18, -1):
        if i not in used:
            return i
    pytest.skip("чөлөөтэй ангиллын id алга")


def test_school_category_list_seed(api):
    r = api.get("/api/school_category")
    assert r.status_code == 200
    data = r.get_json()
    ids = [c["id"] for c in data]
    assert set(range(11, 18)) <= set(ids)
    for c in data:
        assert c["code"] == f"{c['id']:02d}"


def test_school_category_get(api):
    r = api.get("/api/school_category/11")
    assert r.status_code == 200
    assert r.get_json()["code"] == "11" and r.get_json()["full_name"]
    assert api.get("/api/school_category/9999").status_code == 404


def test_school_category_crud_explicit_id(api):
    cid = _free_cat_id(api)
    r = api.post("/api/school_category", json={
        "id": cid, "full_name": "Тест ангилал", "short_name": "ТА",
        "english_name": "Test"})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["id"] == cid and body["code"] == f"{cid:02d}"
    assert body["short_name"] == "ТА"

    assert api.post("/api/school_category",
                    json={"id": cid, "full_name": "Дахин"}).status_code == 409

    r = api.put(f"/api/school_category/{cid}", json={"short_name": "ТБ"})
    assert r.status_code == 200
    assert r.get_json() == {"updated": cid, "fields": ["short_name"]}
    r = api.patch(f"/api/school_category/{cid}", json={"english_name": "Test2"})
    assert r.status_code == 200
    got = api.get(f"/api/school_category/{cid}").get_json()
    assert got["short_name"] == "ТБ" and got["english_name"] == "Test2"

    r = api.delete(f"/api/school_category/{cid}")
    assert r.status_code == 200 and r.get_json() == {"deleted": cid}
    assert api.get(f"/api/school_category/{cid}").status_code == 404


def test_school_category_auto_id(api):
    r = api.post("/api/school_category", json={"full_name": "Авто id"})
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["id"]
    assert isinstance(cid, int)
    assert r.get_json()["full_name"] == "Авто id"
    assert api.delete(f"/api/school_category/{cid}").status_code == 200


@pytest.mark.parametrize("bad", [0, 100, -1, "abc"])
def test_school_category_bad_id_400(api, bad):
    r = api.post("/api/school_category", json={"id": bad, "full_name": "x"})
    assert r.status_code == 400


def test_school_category_validation(api):
    assert api.post("/api/school_category", json={"short_name": "x"}).status_code == 400
    assert api.put("/api/school_category/11", json={"foo": 1}).status_code == 400
    assert api.put("/api/school_category/11").status_code == 400
    assert api.put("/api/school_category/9999",
                   json={"short_name": "x"}).status_code == 404
    assert api.delete("/api/school_category/9999").status_code == 404


@pytest.mark.xfail(reason="BUG: create_au3 уншсан эцэг сумын au1_code-г au1_code-той "
                          "тулгадаггүй — өөр аймгийн au1_code-той баг бүртгэгдэнэ",
                   strict=True)
def test_au3_au1_code_must_match_parent(api, au2):
    _, a2 = au2
    r = api.post("/api/au3", json={"au3_code": _code("C"), "au3_name": "x",
                                   "au1_code": "011", "au2_code": a2})
    assert r.status_code == 400
