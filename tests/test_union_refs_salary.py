"""admin/union/ — лавлахууд ба гишүүний дэд нөөцүүдийн тест — salary_scale, salary_request."""

from conftest import uniq

from _union_refs_helpers import MISSING
import _union_refs_helpers

member = _union_refs_helpers.member   # pytest фикстур (_union_refs_helpers.py-д)


# ============================== salary_scale ==============================
def _new_scale(api, **extra):
    body = {"sector": "СӨБ ба ЕБС", "code": uniq("SS"), "position": "Багш",
            "salary": 1500000}
    body.update(extra)
    r = api.post("/api/salary_scale", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_salary_scale_crud_and_filter(api):
    sc = _new_scale(api, sector="Шинжлэх ухаан")
    sid = sc["id"]
    assert sc["salary"] == 1500000
    assert api.get(f"/api/salary_scale/{sid}").get_json()["code"] == sc["code"]

    filt = api.get("/api/salary_scale", query_string={"sector": "Шинжлэх ухаан"}).get_json()
    assert any(x["id"] == sid for x in filt)
    assert all(x["sector"] == "Шинжлэх ухаан" for x in filt)
    other = api.get("/api/salary_scale", query_string={"sector": "СӨБ ба ЕБС"}).get_json()
    assert not any(x["id"] == sid for x in other)
    assert any(x["id"] == sid for x in api.get("/api/salary_scale").get_json())

    r = api.put(f"/api/salary_scale/{sid}", json={"salary": 2000000})
    assert r.status_code == 200 and r.get_json() == {"updated": sid, "fields": ["salary"]}
    r = api.patch(f"/api/salary_scale/{sid}", json={"position": "Захирал"})
    assert r.status_code == 200
    got = api.get(f"/api/salary_scale/{sid}").get_json()
    assert got["salary"] == 2000000 and got["position"] == "Захирал"

    assert api.delete(f"/api/salary_scale/{sid}").get_json() == {"deleted": sid}
    assert api.get(f"/api/salary_scale/{sid}").status_code == 404


def test_salary_scale_errors(api):
    assert api.post("/api/salary_scale", json={"sector": "СӨБ ба ЕБС"}).status_code == 400
    assert api.post("/api/salary_scale", json={"code": "x"}).status_code == 400
    a = _new_scale(api)
    b = _new_scale(api)
    assert api.post("/api/salary_scale",
                    json={"sector": "СӨБ ба ЕБС", "code": a["code"]}).status_code == 409
    assert api.put(f"/api/salary_scale/{b['id']}", json={"code": a["code"]}).status_code == 409
    assert api.patch(f"/api/salary_scale/{b['id']}", json={"code": a["code"]}).status_code == 409
    assert api.put(f"/api/salary_scale/{a['id']}", json={}).status_code == 400
    assert api.get(f"/api/salary_scale/{MISSING}").status_code == 404
    assert api.put(f"/api/salary_scale/{MISSING}", json={"salary": 1}).status_code == 404
    assert api.patch(f"/api/salary_scale/{MISSING}", json={"salary": 1}).status_code == 404
    assert api.delete(f"/api/salary_scale/{MISSING}").status_code == 404
    api.delete(f"/api/salary_scale/{a['id']}")
    api.delete(f"/api/salary_scale/{b['id']}")


def test_delete_salary_scale_nulls_member(api, member):
    sc = _new_scale(api)
    mid = member["id"]
    assert api.patch(f"/api/member/{mid}", json={"salary_scale_id": sc["id"]}).status_code == 200
    m = api.get(f"/api/member/{mid}").get_json()
    assert m["salary_scale_code"] == sc["code"]
    assert api.delete(f"/api/salary_scale/{sc['id']}").status_code == 200
    assert api.get(f"/api/member/{mid}").get_json()["salary_scale_id"] is None


# ============================= salary_request =============================
def test_salary_request_crud_and_filters(api, member):
    mid = member["id"]
    r = api.post("/api/salary_request", json={"member_id": mid, "salary": 900000,
                                              "sector": "Мэргэжлийн боловсрол",
                                              "note": "анх"})
    assert r.status_code == 201, r.get_json()
    req = r.get_json()
    sid = req["id"]
    assert req["member_id"] == mid
    assert req["status"] == "хүлээгдэж буй"          # DB-ийн анхдагч

    assert api.get(f"/api/salary_request/{sid}").get_json()["id"] == sid
    by_member = api.get("/api/salary_request", query_string={"member_id": mid}).get_json()
    assert [x["id"] for x in by_member] == [sid]

    r = api.put(f"/api/salary_request/{sid}", json={"status": "зөвшөөрсөн"})
    assert r.status_code == 200 and r.get_json() == {"updated": sid, "fields": ["status"]}
    r = api.patch(f"/api/salary_request/{sid}", json={"note": "засав"})
    assert r.status_code == 200
    got = api.get(f"/api/salary_request/{sid}").get_json()
    assert got["status"] == "зөвшөөрсөн" and got["note"] == "засав"

    ok = api.get("/api/salary_request",
                 query_string={"member_id": mid, "status": "зөвшөөрсөн"}).get_json()
    assert [x["id"] for x in ok] == [sid]
    none = api.get("/api/salary_request",
                   query_string={"member_id": mid, "status": "татгалзсан"}).get_json()
    assert none == []
    assert any(x["id"] == sid for x in api.get("/api/salary_request").get_json())

    assert api.delete(f"/api/salary_request/{sid}").get_json() == {"deleted": sid}
    assert api.get(f"/api/salary_request/{sid}").status_code == 404


def test_salary_request_copies_scale(api, member):
    sc = _new_scale(api, sector="Шинжлэх ухаан", position="Эрдэм шинжилгээний ажилтан",
                    salary=1800000)
    r = api.post("/api/salary_request", json={"member_id": member["id"],
                                              "salary_scale_id": sc["id"],
                                              "salary": 1, "sector": "СӨБ ба ЕБС"})
    assert r.status_code == 201
    req = r.get_json()
    assert (req["sector"], req["code"], req["position"], req["salary"]) == \
        (sc["sector"], sc["code"], sc["position"], sc["salary"])

    sc2 = _new_scale(api, salary=2222222)
    r = api.patch(f"/api/salary_request/{req['id']}", json={"salary_scale_id": sc2["id"]})
    assert r.status_code == 200
    assert set(r.get_json()["fields"]) >= {"salary_scale_id", "salary", "code"}
    got = api.get(f"/api/salary_request/{req['id']}").get_json()
    assert got["salary"] == 2222222 and got["code"] == sc2["code"]
    api.delete(f"/api/salary_request/{req['id']}")


def test_salary_request_errors(api, member):
    mid = member["id"]
    assert api.post("/api/salary_request", json={}).status_code == 400
    assert api.post("/api/salary_request", json={"member_id": MISSING}).status_code == 400
    assert api.post("/api/salary_request",
                    json={"member_id": mid, "status": "буруу"}).status_code == 400
    assert api.post("/api/salary_request",
                    json={"member_id": mid, "sector": "буруу"}).status_code == 400
    assert api.post("/api/salary_request",
                    json={"member_id": mid, "salary_scale_id": MISSING}).status_code == 400

    sid = api.post("/api/salary_request", json={"member_id": mid}).get_json()["id"]
    assert api.put(f"/api/salary_request/{sid}", json={"status": "буруу"}).status_code == 400
    assert api.patch(f"/api/salary_request/{sid}", json={"sector": "буруу"}).status_code == 400
    assert api.put(f"/api/salary_request/{sid}",
                   json={"salary_scale_id": MISSING}).status_code == 400
    assert api.put(f"/api/salary_request/{sid}", json={}).status_code == 400
    assert api.get(f"/api/salary_request/{MISSING}").status_code == 404
    assert api.put(f"/api/salary_request/{MISSING}", json={"note": "a"}).status_code == 404
    assert api.patch(f"/api/salary_request/{MISSING}", json={"note": "a"}).status_code == 404
    assert api.delete(f"/api/salary_request/{MISSING}").status_code == 404
    api.delete(f"/api/salary_request/{sid}")
