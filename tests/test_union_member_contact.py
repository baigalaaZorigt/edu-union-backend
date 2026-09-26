"""admin/union/ — horoo / organization / member / contact / member_file — member, contact."""

import os

import pytest

import admin.union.common as union
from conftest import PDF_BYTES

from _union_helpers import AU1, AU2, AU3, make_member, make_org, upload


# ============================== member ==============================
def test_member_crud(api):
    o = make_org(api)
    pos = api.get("/api/position").get_json()[0]
    prof = api.get("/api/profession").get_json()[0]
    ss = api.get("/api/salary_scale").get_json()[0]
    m = make_member(api, o["id"], position_id=pos["id"], profession_id=prof["id"],
                    salary_scale_id=ss["id"], gender="эм", birth_date="1990-05-05",
                    member_status="идэвхтэй", status="баталгаажсан", is_active=True,
                    signature="1", au1_code=AU1, au2_code=AU2, au3_code=AU3,
                    union_card_code="0001")
    assert m["position_name"] == pos["name"] and m["profession_name"] == prof["name"]
    assert m["salary_scale_code"] == ss["code"]
    assert m["is_active"] == 1 and m["signature"] == 1
    mid = m["id"]

    got = api.get(f"/api/member/{mid}").get_json()
    for k in ("educations", "contacts", "rewards", "files"):
        assert got[k] == []

    r = api.put(f"/api/member/{mid}", json={"first_name": "Шинэ"})
    assert r.status_code == 200 and r.get_json()["fields"] == ["first_name"]
    r = api.patch(f"/api/member/{mid}", json={"is_active": 0, "member_status": "түр"})
    assert r.status_code == 200
    got = api.get(f"/api/member/{mid}").get_json()
    assert got["first_name"] == "Шинэ" and got["is_active"] == 0 and got["member_status"] == "түр"

    assert any(x["id"] == mid for x in api.get(f"/api/member?organization_id={o['id']}").get_json())
    assert any(x["id"] == mid for x in
               api.get(f"/api/member?organization_id={o['id']}&is_active=0").get_json())
    assert not any(x["id"] == mid for x in
                   api.get(f"/api/member?organization_id={o['id']}&is_active=1").get_json())
    assert any(x["id"] == mid for x in api.get("/api/member").get_json())

    assert api.delete(f"/api/member/{mid}").status_code == 200
    assert api.get(f"/api/member/{mid}").status_code == 404
    api.delete(f"/api/organization/{o['id']}")


def test_member_card_code(api):
    o = make_org(api)
    m = make_member(api, o["id"], union_card_code="0007")
    assert m["union_card_number"] == o["full_code"] + "0007"
    assert len(m["union_card_number"]) == 9

    # Ижил 4 орон ижил байгууллагад -> 409
    r = api.post("/api/member", json={"organization_id": o["id"], "first_name": "x",
                                      "union_card_code": "0007"})
    assert r.status_code == 409
    m2 = make_member(api, o["id"], union_card_code="0008")
    assert api.put(f"/api/member/{m2['id']}", json={"union_card_code": "0007"}).status_code == 409
    # өөрийн кодоо дахин өгөх нь болно
    assert api.patch(f"/api/member/{m['id']}", json={"union_card_code": "0007"}).status_code == 200
    r = api.patch(f"/api/member/{m2['id']}", json={"union_card_code": "0009"})
    assert r.status_code == 200 and "union_card_number" in r.get_json()["fields"]
    assert api.get(f"/api/member/{m2['id']}").get_json()["union_card_number"] == \
        o["full_code"] + "0009"

    # union_card_number-г шууд өгөх -> 400
    assert api.post("/api/member", json={"organization_id": o["id"], "first_name": "x",
                                         "union_card_number": "123456789"}).status_code == 400
    assert api.put(f"/api/member/{m['id']}",
                   json={"union_card_number": "123456789"}).status_code == 400
    for bad in ("7", "00071", "abcd", 7):
        assert api.post("/api/member", json={"organization_id": o["id"], "first_name": "x",
                                             "union_card_code": bad}).status_code == 400
    api.delete(f"/api/organization/{o['id']}")


def test_member_card_needs_org_code(api):
    r = api.post("/api/organization", json={"name": "кодгүй"})
    assert r.status_code == 201
    o = r.get_json()
    assert api.post("/api/member", json={"organization_id": o["id"], "first_name": "x",
                                         "union_card_code": "0001"}).status_code == 400
    m = make_member(api, o["id"])
    assert m["union_card_number"] is None and m["organization_code"] is None
    assert api.put(f"/api/member/{m['id']}", json={"union_card_code": "0001"}).status_code == 400
    api.delete(f"/api/organization/{o['id']}")


@pytest.mark.parametrize("extra", [
    {"position_id": 999999},
    {"profession_id": 999999},
    {"salary_scale_id": 999999},
    {"au1_code": "999"},
    {"au3_code": "nope"},
    {"is_active": 2},
    {"signature": "yes"},
    {"member_status": ""},
    {"status": 5},
    {"member_status": "   "},
])
def test_member_create_400(api, extra):
    o = make_org(api)
    body = {"organization_id": o["id"], "first_name": "x", **extra}
    assert api.post("/api/member", json=body).status_code == 400
    api.delete(f"/api/organization/{o['id']}")


def test_member_errors(api):
    assert api.post("/api/member", json={"first_name": "x"}).status_code == 400
    assert api.post("/api/member", json={"organization_id": 1}).status_code == 400
    assert api.post("/api/member", json={"organization_id": 999999,
                                         "first_name": "x"}).status_code == 400
    assert api.get("/api/member/999999").status_code == 404
    assert api.put("/api/member/999999", json={"first_name": "x"}).status_code == 404
    assert api.patch("/api/member/999999", json={"union_card_code": "0001"}).status_code == 404
    assert api.delete("/api/member/999999").status_code == 404
    o = make_org(api)
    m = make_member(api, o["id"])
    assert api.put(f"/api/member/{m['id']}", json={"bogus": 1}).status_code == 400
    assert api.patch(f"/api/member/{m['id']}", json={"position_id": 999999}).status_code == 400
    assert api.patch(f"/api/member/{m['id']}", json={"is_active": "x"}).status_code == 400
    api.delete(f"/api/organization/{o['id']}")


def test_member_delete_purges_contacts_and_files(api):
    o = make_org(api)
    m = make_member(api, o["id"])
    c = api.post("/api/contact", json={"owner_type": "member", "owner_id": m["id"],
                                       "type": "утас", "value": "1"}).get_json()
    f = upload(api, m["id"], [("a.pdf", PDF_BYTES)]).get_json()[0]
    path = os.path.join(union.UPLOAD_DIR, f["stored_name"])
    got = api.get(f"/api/member/{m['id']}").get_json()
    assert len(got["contacts"]) == 1 and len(got["files"]) == 1
    api.delete(f"/api/member/{m['id']}")
    assert all(x["id"] != c["id"] for x in api.get("/api/contact").get_json())
    assert not os.path.exists(path)
    assert api.get(f"/api/member_file/{f['id']}").status_code == 404
    api.delete(f"/api/organization/{o['id']}")


# ============================== contact ==============================
def test_contact_crud(api):
    o = make_org(api)
    r = api.post("/api/contact", json={"owner_type": "organization", "owner_id": o["id"],
                                       "type": "утас", "value": "99887766", "note": "ажлын"})
    assert r.status_code == 201
    c = r.get_json()
    assert c["value"] == "99887766" and c["note"] == "ажлын"
    cid = c["id"]

    lst = api.get(f"/api/contact?owner_type=organization&owner_id={o['id']}").get_json()
    assert [x["id"] for x in lst] == [cid]
    assert any(x["id"] == cid for x in api.get("/api/contact").get_json())

    r = api.put(f"/api/contact/{cid}", json={"value": "11"})
    assert r.status_code == 200 and r.get_json()["fields"] == ["value"]
    r = api.patch(f"/api/contact/{cid}", json={"type": "факс", "note": None})
    assert r.status_code == 200
    got = api.get(f"/api/contact?owner_type=organization&owner_id={o['id']}").get_json()[0]
    assert got["value"] == "11" and got["type"] == "факс" and got["note"] is None

    assert api.delete(f"/api/contact/{cid}").status_code == 200
    assert api.delete(f"/api/contact/{cid}").status_code == 404
    api.delete(f"/api/organization/{o['id']}")


def test_contact_errors(api):
    o = make_org(api)
    base = {"owner_type": "organization", "owner_id": o["id"], "type": "утас", "value": "1"}
    for missing in ("owner_type", "owner_id", "type", "value"):
        body = dict(base)
        body.pop(missing)
        assert api.post("/api/contact", json=body).status_code == 400
    assert api.post("/api/contact", json={**base, "owner_type": "user"}).status_code == 400
    assert api.post("/api/contact", json={**base, "type": "телеграм"}).status_code == 400
    assert api.post("/api/contact", json={**base, "owner_id": 999999}).status_code == 400
    assert api.post("/api/contact", json={**base, "owner_type": "member"}).status_code in (201, 400)
    c = api.post("/api/contact", json=base).get_json()
    assert api.put(f"/api/contact/{c['id']}", json={"type": "бусад"}).status_code == 400
    assert api.put(f"/api/contact/{c['id']}", json={"owner_id": 5}).status_code == 400
    assert api.put("/api/contact/999999", json={"value": "x"}).status_code == 404
    assert api.patch("/api/contact/999999", json={"value": "x"}).status_code == 404
    assert api.get(f"/api/contact/{c['id']}").status_code == 405
    api.delete(f"/api/organization/{o['id']}")


def test_contact_on_member(api):
    o = make_org(api)
    m = make_member(api, o["id"])
    for t, v in (("утас", "1"), ("утас", "2"), ("и-мэйл", "x@y.mn")):
        assert api.post("/api/contact", json={"owner_type": "member", "owner_id": m["id"],
                                              "type": t, "value": v}).status_code == 201
    assert len(api.get(f"/api/member/{m['id']}").get_json()["contacts"]) == 3
    api.delete(f"/api/organization/{o['id']}")
