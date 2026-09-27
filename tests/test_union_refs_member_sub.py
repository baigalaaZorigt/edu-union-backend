"""admin/union/ — лавлахууд ба гишүүний дэд нөөцүүдийн тест — member_education, member_reward, auth."""

import pytest

from conftest import uniq

from _union_refs_helpers import MISSING, _new_ref
import _union_refs_helpers

member = _union_refs_helpers.member   # pytest фикстур (_union_refs_helpers.py-д)


# ============================ member_education ============================
def test_member_education_crud(api, member):
    mid = member["id"]
    degrees = api.get("/api/education_degree").get_json()
    d1, d2 = degrees[0], degrees[1]
    r = api.post("/api/member_education", json={
        "member_id": mid, "education_degree_id": d1["id"], "school": "МУБИС",
        "profession": "Багш", "graduation_year": 2010})
    assert r.status_code == 201, r.get_json()
    eid = r.get_json()["id"]
    assert r.get_json()["school"] == "МУБИС"

    got = api.get(f"/api/member_education/{eid}")
    assert got.status_code == 200 and str(got.get_json()["graduation_year"]) == "2010"

    lst = api.get("/api/member_education", query_string={"member_id": mid}).get_json()
    assert [x["id"] for x in lst] == [eid]
    assert lst[0]["education_degree_name"] == d1["name"]
    assert any(x["id"] == eid for x in api.get("/api/member_education").get_json())

    r = api.put(f"/api/member_education/{eid}", json={"education_degree_id": d2["id"]})
    assert r.status_code == 200
    assert r.get_json() == {"updated": eid, "fields": ["education_degree_id"]}
    r = api.patch(f"/api/member_education/{eid}", json={"school": "МУИС"})
    assert r.status_code == 200
    lst = api.get("/api/member_education", query_string={"member_id": mid}).get_json()
    assert lst[0]["education_degree_name"] == d2["name"] and lst[0]["school"] == "МУИС"

    # гишүүний дэлгэрэнгүйд шигтгэгдэнэ
    detail = api.get(f"/api/member/{mid}").get_json()
    assert any(e["id"] == eid for e in detail["educations"])

    assert api.delete(f"/api/member_education/{eid}").get_json() == {"deleted": eid}
    assert api.get(f"/api/member_education/{eid}").status_code == 404


def test_member_education_errors(api, member):
    mid = member["id"]
    assert api.post("/api/member_education", json={}).status_code == 400
    assert api.post("/api/member_education", json={"member_id": MISSING}).status_code == 400
    assert api.post("/api/member_education",
                    json={"member_id": mid, "education_degree_id": MISSING}).status_code == 400
    eid = api.post("/api/member_education", json={"member_id": mid}).get_json()["id"]
    assert api.put(f"/api/member_education/{eid}", json={}).status_code == 400
    assert api.patch(f"/api/member_education/{eid}",
                     json={"education_degree_id": MISSING}).status_code == 400
    assert api.get(f"/api/member_education/{MISSING}").status_code == 404
    assert api.put(f"/api/member_education/{MISSING}", json={"school": "a"}).status_code == 404
    assert api.patch(f"/api/member_education/{MISSING}", json={"school": "a"}).status_code == 404
    assert api.delete(f"/api/member_education/{MISSING}").status_code == 404


def test_member_education_cascade_on_member_delete(api, member):
    eid = api.post("/api/member_education", json={"member_id": member["id"]}).get_json()["id"]
    assert api.delete(f"/api/member/{member['id']}").status_code == 200
    assert api.get(f"/api/member_education/{eid}").status_code == 404


def test_delete_degree_blocked_while_used(api, member):
    deg = api.post("/api/education_degree", json={"name": uniq("Түр зэрэг ")}).get_json()
    eid = api.post("/api/member_education", json={
        "member_id": member["id"], "education_degree_id": deg["id"]}).get_json()["id"]
    r = api.delete(f"/api/education_degree/{deg['id']}")
    assert r.status_code == 409 and "1 гишүүний боловсрол" in r.get_json()["error"]
    assert api.get(f"/api/member_education/{eid}").get_json()["education_degree_id"] == deg["id"]
    api.delete(f"/api/member_education/{eid}")
    assert api.delete(f"/api/education_degree/{deg['id']}").status_code == 200


# ============================== member_reward ==============================
def test_member_reward_crud_and_filters(api, member):
    mid = member["id"]
    rt1 = _new_ref(api, "reward_type")
    rt2 = _new_ref(api, "reward_type")
    r = api.post("/api/member_reward", json={
        "member_id": mid, "reward_type_id": rt1["id"],
        "description": "Хүндэт жуух", "reward_date": "2024-05-01"})
    assert r.status_code == 201, r.get_json()
    rw = r.get_json()
    rid = rw["id"]
    assert rw["reward_type_name"] == rt1["name"] and rw["reward_type_code"] == rt1["code"]
    rid2 = api.post("/api/member_reward", json={
        "member_id": mid, "reward_type_id": rt2["id"]}).get_json()["id"]

    got = api.get(f"/api/member_reward/{rid}").get_json()
    assert got["reward_date"] == "2024-05-01" and got["reward_type_name"] == rt1["name"]

    lst = api.get("/api/member_reward", query_string={"member_id": mid}).get_json()
    assert [x["id"] for x in lst] == [rid, rid2]
    lst = api.get("/api/member_reward", query_string={"reward_type_id": rt2["id"]}).get_json()
    assert [x["id"] for x in lst] == [rid2]
    lst = api.get("/api/member_reward",
                  query_string={"member_id": mid, "reward_type_id": rt1["id"]}).get_json()
    assert [x["id"] for x in lst] == [rid]
    assert any(x["id"] == rid for x in api.get("/api/member_reward").get_json())

    detail = api.get(f"/api/member/{mid}").get_json()
    assert {x["id"] for x in detail["rewards"]} == {rid, rid2}

    r = api.put(f"/api/member_reward/{rid}", json={"reward_type_id": rt2["id"]})
    assert r.status_code == 200
    assert r.get_json() == {"updated": rid, "fields": ["reward_type_id"]}
    r = api.patch(f"/api/member_reward/{rid}", json={"description": "Медаль"})
    assert r.status_code == 200
    got = api.get(f"/api/member_reward/{rid}").get_json()
    assert got["reward_type_name"] == rt2["name"] and got["description"] == "Медаль"

    # шагнал заасан төрлийг устгах -> 409 (2 шагнал), шагнал хөндөгдөхгүй
    r = api.delete(f"/api/reward_type/{rt2['id']}")
    assert r.status_code == 409 and r.get_json()["references"][0]["count"] == 2
    assert api.get(f"/api/member_reward/{rid}").get_json()["reward_type_id"] == rt2["id"]

    assert api.delete(f"/api/member_reward/{rid}").get_json() == {"deleted": rid}
    assert api.get(f"/api/member_reward/{rid}").status_code == 404
    api.delete(f"/api/member_reward/{rid2}")
    assert api.delete(f"/api/reward_type/{rt2['id']}").status_code == 200   # холбоосгүй болсон
    api.delete(f"/api/reward_type/{rt1['id']}")


def test_member_reward_errors(api, member):
    mid = member["id"]
    assert api.post("/api/member_reward", json={}).status_code == 400
    assert api.post("/api/member_reward", json={"member_id": MISSING}).status_code == 400
    assert api.post("/api/member_reward",
                    json={"member_id": mid, "reward_type_id": MISSING}).status_code == 400
    rid = api.post("/api/member_reward", json={"member_id": mid}).get_json()["id"]
    assert api.put(f"/api/member_reward/{rid}", json={}).status_code == 400
    assert api.patch(f"/api/member_reward/{rid}",
                     json={"reward_type_id": MISSING}).status_code == 400
    assert api.get(f"/api/member_reward/{MISSING}").status_code == 404
    assert api.put(f"/api/member_reward/{MISSING}", json={"description": "a"}).status_code == 404
    assert api.patch(f"/api/member_reward/{MISSING}",
                     json={"description": "a"}).status_code == 404
    assert api.delete(f"/api/member_reward/{MISSING}").status_code == 404
    api.delete(f"/api/member_reward/{rid}")


# ================================ auth ================================
@pytest.mark.parametrize("path", [
    "/api/education_degree", "/api/position", "/api/profession", "/api/reward_type",
    "/api/structure", "/api/salary_scale", "/api/salary_request",
    "/api/member_education", "/api/member_reward",
])
def test_requires_token(anon, path):
    assert anon.get(path).status_code == 401
    assert anon.post(path, json={"name": "x"}).status_code == 401


def test_permission_enforced(make_user):
    u, _ = make_user(["position.read"])
    assert u.get("/api/position").status_code == 200
    assert u.post("/api/position", json={"name": "x"}).status_code == 403
    assert u.get("/api/profession").status_code == 403
    assert u.get("/api/member_reward").status_code == 403
