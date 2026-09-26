"""admin/union/ — лавлахууд ба гишүүний дэд нөөцүүдийн тест — кодтой лавлахууд (4 хүснэгт), education_degree."""

import pytest

from conftest import uniq

from _union_refs_helpers import CODED_REFS, MISSING, _new_ref
import _union_refs_helpers

member = _union_refs_helpers.member   # pytest фикстур (_union_refs_helpers.py-д)


# ====================== кодтой лавлахууд (4 хүснэгт) ======================
@pytest.mark.parametrize("table", CODED_REFS)
def test_coded_ref_list_seeded(api, table):
    r = api.get(f"/api/{table}")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list) and data
    assert {"id", "code", "name"} <= set(data[0])


@pytest.mark.parametrize("table", CODED_REFS)
def test_coded_ref_crud(api, table):
    row = _new_ref(api, table)
    rid = row["id"]
    got = api.get(f"/api/{table}/{rid}")
    assert got.status_code == 200
    assert got.get_json()["code"] == row["code"]
    assert any(x["id"] == rid for x in api.get(f"/api/{table}").get_json())

    # PUT — зөвхөн name (хэсэгчилсэн): code хэвээр үлдэнэ
    r = api.put(f"/api/{table}/{rid}", json={"name": "Шинэ нэр"})
    assert r.status_code == 200
    assert r.get_json()["name"] == "Шинэ нэр"
    assert r.get_json()["code"] == row["code"]

    # PATCH — зөвхөн code
    new_code = uniq("p")
    r = api.patch(f"/api/{table}/{rid}", json={"code": new_code})
    assert r.status_code == 200
    assert r.get_json()["code"] == new_code
    assert r.get_json()["name"] == "Шинэ нэр"

    # өөрийн кодыг дахин илгээх нь 409 биш
    assert api.put(f"/api/{table}/{rid}", json={"code": new_code}).status_code == 200

    r = api.delete(f"/api/{table}/{rid}")
    assert r.status_code == 200
    assert r.get_json() == {"deleted": rid}
    assert api.get(f"/api/{table}/{rid}").status_code == 404
    assert api.delete(f"/api/{table}/{rid}").status_code == 404


@pytest.mark.parametrize("table", CODED_REFS)
def test_coded_ref_create_without_code(api, table):
    r = api.post(f"/api/{table}", json={"name": uniq("Кодгүй ")})
    assert r.status_code == 201
    assert r.get_json()["code"] is None
    api.delete(f"/api/{table}/{r.get_json()['id']}")


@pytest.mark.parametrize("table", CODED_REFS)
def test_coded_ref_validation(api, table):
    assert api.post(f"/api/{table}", json={"code": "x"}).status_code == 400   # name алга
    assert api.post(f"/api/{table}", json={}).status_code == 400
    assert api.get(f"/api/{table}/{MISSING}").status_code == 404
    assert api.put(f"/api/{table}/{MISSING}", json={"name": "a"}).status_code == 404
    assert api.patch(f"/api/{table}/{MISSING}", json={"name": "a"}).status_code == 404
    assert api.delete(f"/api/{table}/{MISSING}").status_code == 404

    row = _new_ref(api, table)
    rid = row["id"]
    assert api.put(f"/api/{table}/{rid}", json={}).status_code == 400          # талбаргүй
    assert api.put(f"/api/{table}/{rid}", json={"other": 1}).status_code == 400
    assert api.patch(f"/api/{table}/{rid}", json={"name": "  "}).status_code == 400
    assert api.put(f"/api/{table}/{rid}", json={"name": None}).status_code == 400
    api.delete(f"/api/{table}/{rid}")


@pytest.mark.parametrize("table", CODED_REFS)
def test_coded_ref_code_unique_409(api, table):
    a = _new_ref(api, table)
    b = _new_ref(api, table)
    # үүсгэхэд давхардсан код
    assert api.post(f"/api/{table}", json={"code": a["code"], "name": "x"}).status_code == 409
    # засахад өөр мөрийн код
    assert api.put(f"/api/{table}/{b['id']}", json={"code": a["code"]}).status_code == 409
    assert api.patch(f"/api/{table}/{b['id']}", json={"code": a["code"]}).status_code == 409
    # давхардсан id
    assert api.post(f"/api/{table}",
                    json={"id": a["id"], "code": uniq("z"), "name": "x"}).status_code == 409
    api.delete(f"/api/{table}/{a['id']}")
    api.delete(f"/api/{table}/{b['id']}")


def test_coded_ref_explicit_id(api):
    rid = 900000 + int(uniq("")[-4:])
    r = api.post("/api/position", json={"id": rid, "code": uniq("e"), "name": "Тусгай id"})
    assert r.status_code == 201
    assert r.get_json()["id"] == rid
    assert api.delete(f"/api/position/{rid}").status_code == 200


def test_delete_position_profession_nulls_member(api, member):
    pos = _new_ref(api, "position")
    prof = _new_ref(api, "profession")
    mid = member["id"]
    r = api.put(f"/api/member/{mid}",
                json={"position_id": pos["id"], "profession_id": prof["id"]})
    assert r.status_code == 200, r.get_json()
    m = api.get(f"/api/member/{mid}").get_json()
    assert m["position_id"] == pos["id"] and m["position_name"] == pos["name"]
    assert m["profession_id"] == prof["id"] and m["profession_name"] == prof["name"]

    assert api.delete(f"/api/position/{pos['id']}").status_code == 200
    assert api.delete(f"/api/profession/{prof['id']}").status_code == 200
    m = api.get(f"/api/member/{mid}").get_json()
    assert m["position_id"] is None and m["position_name"] is None
    assert m["profession_id"] is None and m["profession_name"] is None


def test_delete_structure_nulls_org_and_user(api):
    st = _new_ref(api, "structure")
    r = api.post("/api/organization",
                 json={"name": uniq("Бүтэцтэй "), "structure_id": st["id"]})
    assert r.status_code == 201
    org = r.get_json()
    assert org["structure_id"] == st["id"]
    assert org["structure_name"] == st["name"] and org["structure_code"] == st["code"]

    r = api.post("/api/user", json={"username": uniq("stu"), "password": "Pass1234",
                                    "last_name": "Т", "first_name": "Х",
                                    "structure_id": st["id"]})
    assert r.status_code == 201, r.get_json()
    uid = r.get_json()["id"]
    assert api.get(f"/api/user/{uid}").get_json()["structure_id"] == st["id"]

    assert api.delete(f"/api/structure/{st['id']}").status_code == 200
    got = api.get(f"/api/organization/{org['id']}").get_json()
    assert got["structure_id"] is None and got["structure_name"] is None
    assert api.get(f"/api/user/{uid}").get_json()["structure_id"] is None
    api.delete(f"/api/user/{uid}")
    api.delete(f"/api/organization/{org['id']}")


def test_organization_bad_structure_400(api):
    r = api.post("/api/organization", json={"name": "x", "structure_id": MISSING})
    assert r.status_code == 400


# ============================ education_degree ============================
def test_education_degree_crud(api):
    lst = api.get("/api/education_degree")
    assert lst.status_code == 200 and lst.get_json()
    r = api.post("/api/education_degree", json={"name": uniq("Зэрэг ")})
    assert r.status_code == 201
    eid = r.get_json()["id"]
    assert api.get(f"/api/education_degree/{eid}").get_json()["id"] == eid

    r = api.put(f"/api/education_degree/{eid}", json={"name": "Доктор+"})
    assert r.status_code == 200 and r.get_json() == {"id": eid, "name": "Доктор+"}
    r = api.patch(f"/api/education_degree/{eid}", json={"name": "Доктор++"})
    assert r.status_code == 200
    assert api.get(f"/api/education_degree/{eid}").get_json()["name"] == "Доктор++"

    assert api.delete(f"/api/education_degree/{eid}").get_json() == {"deleted": eid}
    assert api.get(f"/api/education_degree/{eid}").status_code == 404


def test_education_degree_errors(api):
    first = api.get("/api/education_degree").get_json()[0]["id"]
    assert api.post("/api/education_degree", json={}).status_code == 400
    assert api.post("/api/education_degree",
                    json={"id": first, "name": "dup"}).status_code == 409
    assert api.get(f"/api/education_degree/{MISSING}").status_code == 404
    assert api.put(f"/api/education_degree/{MISSING}", json={"name": "a"}).status_code == 404
    assert api.patch(f"/api/education_degree/{MISSING}", json={"name": "a"}).status_code == 404
    assert api.put(f"/api/education_degree/{first}", json={}).status_code == 400
    assert api.delete(f"/api/education_degree/{MISSING}").status_code == 404
