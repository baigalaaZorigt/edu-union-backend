"""admin/union/ — horoo / organization / member / contact / member_file — horoo, organization."""

import os

import pytest

import admin.union.common as union
from conftest import uniq, PDF_BYTES

from _union_helpers import AU1, AU2, AU3, CAT, free_org_code, make_member, make_org, upload


# ============================== horoo ==============================
def test_horoo_crud(api):
    r = api.post("/api/horoo", json={"holboo_id": 1, "name": uniq("Хороо "),
                                     "type": "салбар", "founded_date": "2000-01-01"})
    assert r.status_code == 201
    h = r.get_json()
    assert h["holboo_id"] == 1 and h["type"] == "салбар"
    hid = h["id"]

    assert any(x["id"] == hid for x in api.get("/api/horoo").get_json())
    assert any(x["id"] == hid for x in api.get("/api/horoo?holboo_id=1").get_json())
    assert api.get("/api/horoo?holboo_id=999999").get_json() == []

    got = api.get(f"/api/horoo/{hid}").get_json()
    assert got["contacts"] == []

    r = api.put(f"/api/horoo/{hid}", json={"name": "Шинэ нэр"})
    assert r.status_code == 200 and r.get_json()["fields"] == ["name"]
    r = api.patch(f"/api/horoo/{hid}", json={"registration_number": "123"})
    assert r.status_code == 200
    got = api.get(f"/api/horoo/{hid}").get_json()
    assert got["name"] == "Шинэ нэр" and got["registration_number"] == "123"

    assert api.delete(f"/api/horoo/{hid}").status_code == 200
    assert api.get(f"/api/horoo/{hid}").status_code == 404


def test_horoo_errors(api):
    assert api.post("/api/horoo", json={"name": "x"}).status_code == 400
    assert api.post("/api/horoo", json={"holboo_id": 999999, "name": "x"}).status_code == 400
    assert api.post("/api/horoo").status_code == 400
    assert api.get("/api/horoo/999999").status_code == 404
    assert api.put("/api/horoo/999999", json={"name": "x"}).status_code == 404
    assert api.patch("/api/horoo/999999", json={"name": "x"}).status_code == 404
    assert api.delete("/api/horoo/999999").status_code == 404
    h = api.post("/api/horoo", json={"holboo_id": 1, "name": "x"}).get_json()
    assert api.put(f"/api/horoo/{h['id']}", json={"bogus": 1}).status_code == 400
    assert api.delete(f"/api/horoo/{h['id']}").status_code == 200


def test_horoo_delete_purges_contacts(api):
    h = api.post("/api/horoo", json={"holboo_id": 1, "name": "x"}).get_json()
    c = api.post("/api/contact", json={"owner_type": "horoo", "owner_id": h["id"],
                                       "type": "утас", "value": "99112233"}).get_json()
    assert len(api.get(f"/api/horoo/{h['id']}").get_json()["contacts"]) == 1
    api.delete(f"/api/horoo/{h['id']}")
    assert all(x["id"] != c["id"] for x in api.get("/api/contact").get_json())


def test_horoo_requires_token(anon):
    assert anon.get("/api/horoo").status_code == 401


# ========================== organization ==========================
def test_org_create_and_read(api):
    st = api.get("/api/structure").get_json()[0]["id"]
    o = make_org(api, name="Тест сургууль", structure_id=st, au1_code=AU1, au2_code=AU2,
                 au3_code=AU3, phone1="99001122", email="a@b.mn", contact_name="Болд")
    assert o["full_code"] == f"{CAT:02d}{o['org_code']}"
    assert o["school_category_code"] == f"{CAT:02d}"
    assert o["school_category_name"] and o["structure_name"]
    assert o["phone1"] == "99001122"

    got = api.get(f"/api/organization/{o['id']}").get_json()
    assert got["total_members"] == 0 and got["contacts"] == []

    lst = api.get("/api/organization").get_json()
    assert any(x["id"] == o["id"] for x in lst)
    assert all("total_members" in x for x in lst)
    f = api.get(f"/api/organization?school_category_id={CAT}&structure_id={st}").get_json()
    assert any(x["id"] == o["id"] for x in f)
    assert all(x["school_category_id"] == CAT and x["structure_id"] == st for x in f)
    assert not any(x["id"] == o["id"] for x in
                   api.get("/api/organization?school_category_id=11").get_json())
    api.delete(f"/api/organization/{o['id']}")


def test_org_category_string_and_empty(api):
    code = free_org_code(api, CAT)
    r = api.post("/api/organization", json={"name": "x", "school_category_id": str(CAT),
                                            "org_code": code})
    assert r.status_code == 201
    o = r.get_json()
    assert o["school_category_id"] == CAT
    r = api.post("/api/organization", json={"name": "y", "school_category_id": "",
                                            "org_code": "123"})
    assert r.status_code == 201
    o2 = r.get_json()
    assert o2["school_category_id"] is None
    assert o2["full_code"] is None and o2["school_category_code"] is None
    api.delete(f"/api/organization/{o['id']}")
    api.delete(f"/api/organization/{o2['id']}")


@pytest.mark.parametrize("body", [
    {},
    {"school_category_id": CAT},                                   # name дутуу
    {"name": "x", "org_code": "12"},                               # 2 орон
    {"name": "x", "org_code": "1234"},                             # 4 орон
    {"name": "x", "org_code": "ab1"},                              # цифр биш
    {"name": "x", "school_category_id": "abc"},                    # тоо биш
    {"name": "x", "school_category_id": 999},                      # лавлахад алга
    {"name": "x", "structure_id": 999999},
    {"name": "x", "au1_code": "999"},
    {"name": "x", "au2_code": "99999"},
    {"name": "x", "au3_code": "9999999"},
])
def test_org_create_400(api, body):
    assert api.post("/api/organization", json=body).status_code == 400


def test_org_code_collision_409(api):
    o = make_org(api)
    r = api.post("/api/organization", json={"name": "dup", "school_category_id": CAT,
                                            "org_code": o["org_code"]})
    assert r.status_code == 409
    # Өөр ангилалд ижил код — зөвшөөрнө
    other = 17
    if o["org_code"] not in {x["org_code"] for x in
                             api.get(f"/api/organization?school_category_id={other}").get_json()}:
        r = api.post("/api/organization", json={"name": "ok", "school_category_id": other,
                                                "org_code": o["org_code"]})
        assert r.status_code == 201
        api.delete(f"/api/organization/{r.get_json()['id']}")
    # Засахад өөр байгууллагын кодыг авбал 409
    o2 = make_org(api)
    assert api.put(f"/api/organization/{o2['id']}",
                   json={"org_code": o["org_code"]}).status_code == 409
    # Өөрийн кодоо дахин илгээх нь 409 биш
    assert api.patch(f"/api/organization/{o2['id']}",
                     json={"org_code": o2["org_code"]}).status_code == 200
    api.delete(f"/api/organization/{o['id']}")
    api.delete(f"/api/organization/{o2['id']}")


def test_org_update_put_patch_and_errors(api):
    o = make_org(api)
    oid = o["id"]
    r = api.put(f"/api/organization/{oid}", json={"name": "PUT нэр"})
    assert r.status_code == 200 and r.get_json() == {"updated": oid, "fields": ["name"]}
    r = api.patch(f"/api/organization/{oid}", json={"email": "p@x.mn", "phone2": "88"})
    assert r.status_code == 200
    got = api.get(f"/api/organization/{oid}").get_json()
    assert got["name"] == "PUT нэр" and got["email"] == "p@x.mn" and got["phone2"] == "88"

    assert api.put(f"/api/organization/{oid}", json={"bogus": 1}).status_code == 400
    assert api.put(f"/api/organization/{oid}", json={"org_code": "1"}).status_code == 400
    assert api.patch(f"/api/organization/{oid}",
                     json={"school_category_id": 999}).status_code == 400
    assert api.patch(f"/api/organization/{oid}", json={"au2_code": "nope"}).status_code == 400
    assert api.put(f"/api/organization/{oid}", data="notjson",
                   content_type="application/json").status_code == 400
    assert api.get("/api/organization/999999").status_code == 404
    assert api.put("/api/organization/999999", json={"name": "x"}).status_code == 404
    assert api.delete("/api/organization/999999").status_code == 404
    assert api.post(f"/api/organization/{oid}", json={}).status_code == 405
    assert api.delete(f"/api/organization/{oid}").status_code == 200
    assert api.get(f"/api/organization/{oid}").status_code == 404


def test_org_stats(api):
    o = make_org(api)
    make_member(api, o["id"], gender="эм", birth_date="2005-01-01")
    make_member(api, o["id"], gender="эр", birth_date="1970-01-01")
    make_member(api, o["id"], gender="эм")
    got = api.get(f"/api/organization/{o['id']}").get_json()
    assert (got["total_members"], got["female_members"], got["under35_members"]) == (3, 2, 1)
    row = next(x for x in api.get("/api/organization").get_json() if x["id"] == o["id"])
    assert row["total_members"] == 3
    api.delete(f"/api/organization/{o['id']}")


def test_org_recompute_cards(api):
    o = make_org(api)
    m = make_member(api, o["id"], union_card_code="0042")
    assert m["union_card_number"] == f"{CAT:02d}{o['org_code']}0042"
    assert m["organization_code"] == o["full_code"]

    new_code = free_org_code(api, CAT)
    assert api.patch(f"/api/organization/{o['id']}",
                     json={"org_code": new_code}).status_code == 200
    got = api.get(f"/api/member/{m['id']}").get_json()
    assert got["union_card_number"] == f"{CAT:02d}{new_code}0042"

    other = 17
    code17 = free_org_code(api, other)
    assert api.put(f"/api/organization/{o['id']}",
                   json={"school_category_id": other, "org_code": code17}).status_code == 200
    got = api.get(f"/api/member/{m['id']}").get_json()
    assert got["union_card_number"] == f"{other:02d}{code17}0042"

    # Ангилалыг хоосолбол батламжийн дугаар NULL болно (union_card_code үлдэнэ)
    assert api.patch(f"/api/organization/{o['id']}",
                     json={"school_category_id": ""}).status_code == 200
    got = api.get(f"/api/member/{m['id']}").get_json()
    assert got["union_card_number"] is None and got["union_card_code"] == "0042"
    api.delete(f"/api/organization/{o['id']}")


def test_org_delete_cascades_members_contacts_files(api):
    o = make_org(api)
    m = make_member(api, o["id"])
    c1 = api.post("/api/contact", json={"owner_type": "organization", "owner_id": o["id"],
                                        "type": "факс", "value": "7011"}).get_json()
    c2 = api.post("/api/contact", json={"owner_type": "member", "owner_id": m["id"],
                                        "type": "и-мэйл", "value": "m@x.mn"}).get_json()
    f = upload(api, m["id"], [("a.pdf", PDF_BYTES)]).get_json()[0]
    path = os.path.join(union.UPLOAD_DIR, f["stored_name"])
    assert os.path.isfile(path)
    assert len(api.get(f"/api/organization/{o['id']}").get_json()["contacts"]) == 1

    assert api.delete(f"/api/organization/{o['id']}").status_code == 200
    assert api.get(f"/api/member/{m['id']}").status_code == 404
    ids = {x["id"] for x in api.get("/api/contact").get_json()}
    assert c1["id"] not in ids and c2["id"] not in ids
    assert api.get(f"/api/member_file/{f['id']}").status_code == 404
    assert not os.path.exists(path)


def test_org_not_owned_by_horoo(api):
    """Хороо устгахад байгууллага устахгүй (horoo_id хасагдсан)."""
    h = api.post("/api/horoo", json={"holboo_id": 1, "name": "x"}).get_json()
    o = make_org(api, horoo_id=h["id"])        # үл тоогдох талбар
    assert "horoo_id" not in o
    api.delete(f"/api/horoo/{h['id']}")
    assert api.get(f"/api/organization/{o['id']}").status_code == 200
    api.delete(f"/api/organization/{o['id']}")
