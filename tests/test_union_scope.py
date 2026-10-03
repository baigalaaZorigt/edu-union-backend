"""admin/union/ — horoo / organization / member / contact / member_file — хамрах хүрээ."""

import pytest

from conftest import MEMBER_REQ, uniq

from _union_helpers import AU1, AU2, make_member, make_org


# ============================ хамрах хүрээ ============================
ORG_MEMBER_PERMS = [f"{r}.{a}" for r in ("organization", "member")
                    for a in ("read", "create", "update", "delete")]


@pytest.fixture
def two_orgs(api):
    """Хүрээнд (ЕБС=12, 01101) болон хүрээнээс гадуур (ЕБС=12, 01104) байгууллага + гишүүд."""
    ins = make_org(api, cat=12, au1_code=AU1, au2_code=AU2)
    out = make_org(api, cat=12, au1_code=AU1, au2_code="01104")
    m_in = make_member(api, ins["id"])
    m_out = make_member(api, out["id"])
    yield ins, out, m_in, m_out
    api.delete(f"/api/organization/{ins['id']}")
    api.delete(f"/api/organization/{out['id']}")


def _set_scope(api, uid, body):
    r = api.put(f"/api/user/{uid}/scope", json=body)
    assert r.status_code == 200, r.get_json()


def _check_scope(u, ins, out, m_in, m_out):
    orgs = {o["id"] for o in u.get("/api/organization").get_json()}
    assert ins["id"] in orgs and out["id"] not in orgs
    mems = {m["id"] for m in u.get("/api/member").get_json()}
    assert m_in["id"] in mems and m_out["id"] not in mems

    assert u.get(f"/api/organization/{ins['id']}").status_code == 200
    assert u.get(f"/api/organization/{out['id']}").status_code == 403
    assert u.put(f"/api/organization/{out['id']}", json={"name": "x"}).status_code == 403
    assert u.patch(f"/api/organization/{out['id']}", json={"name": "x"}).status_code == 403
    assert u.delete(f"/api/organization/{out['id']}").status_code == 403

    assert u.get(f"/api/member/{m_in['id']}").status_code == 200
    assert u.get(f"/api/member/{m_out['id']}").status_code == 403
    assert u.put(f"/api/member/{m_out['id']}", json={"first_name": "x"}).status_code == 403
    assert u.patch(f"/api/member/{m_out['id']}", json={"first_name": "x"}).status_code == 403
    assert u.delete(f"/api/member/{m_out['id']}").status_code == 403
    assert u.post("/api/member", json={**MEMBER_REQ, "organization_id": out["id"],
                                       "first_name": "x"}).status_code == 403

    assert u.patch(f"/api/member/{m_in['id']}", json={"first_name": "OK"}).status_code == 200
    r = u.post("/api/member", json={**MEMBER_REQ, "organization_id": ins["id"], "first_name": "шинэ"})
    assert r.status_code == 201
    assert u.delete(f"/api/member/{r.get_json()['id']}").status_code == 200


def test_scope_specialist_category_district(api, make_user, two_orgs):
    ins, out, m_in, m_out = two_orgs
    u, user = make_user(ORG_MEMBER_PERMS)
    _set_scope(api, user["id"], {"school_type": "general", "district_au2_code": AU2})
    _check_scope(u, ins, out, m_in, m_out)
    orgs = u.get("/api/organization").get_json()
    assert all(o["school_category_id"] == 12 and o["au2_code"] == AU2 for o in orgs)
    # хүрээнээс гадуур ангилал (16) бүр харагдахгүй
    other = make_org(api)
    assert u.get(f"/api/organization/{other['id']}").status_code == 403
    api.delete(f"/api/organization/{other['id']}")


def test_scope_specialist_rural(api, make_user, two_orgs):
    ins, out, m_in, m_out = two_orgs
    u, user = make_user(ORG_MEMBER_PERMS)
    _set_scope(api, user["id"], {"school_type": "rural", "organization_ids": [ins["id"]]})
    _check_scope(u, ins, out, m_in, m_out)
    assert [o["id"] for o in u.get("/api/organization").get_json()] == [ins["id"]]


def test_scope_rural_empty_sees_nothing(api, make_user, two_orgs):
    u, user = make_user(ORG_MEMBER_PERMS)
    _set_scope(api, user["id"], {"school_type": "rural", "organization_ids": []})
    assert u.get("/api/organization").get_json() == []
    assert u.get("/api/member").get_json() == []


def test_scope_school_manager(api, make_user, two_orgs):
    ins, out, m_in, m_out = two_orgs
    u, user = make_user(ORG_MEMBER_PERMS, role_name=uniq("Сургуулийн менежер "))
    _set_scope(api, user["id"], {"organization_id": ins["id"]})
    _check_scope(u, ins, out, m_in, m_out)
    assert [o["id"] for o in u.get("/api/organization").get_json()] == [ins["id"]]
    assert {m["organization_id"] for m in u.get("/api/member").get_json()} == {ins["id"]}


def test_no_scope_sees_everything(api, make_user, two_orgs):
    ins, out, m_in, m_out = two_orgs
    u, _ = make_user(["organization.read", "member.read"])
    orgs = {o["id"] for o in u.get("/api/organization").get_json()}
    assert {ins["id"], out["id"]} <= orgs
    assert u.get(f"/api/member/{m_out['id']}").status_code == 200


def test_permissions_required(make_user):
    u, _ = make_user(["organization.read"])
    assert u.get("/api/organization").status_code == 200
    assert u.post("/api/organization", json={"name": "x"}).status_code == 403
    assert u.get("/api/member").status_code == 403
    assert u.get("/api/horoo").status_code == 403
    assert u.get("/api/contact").status_code == 403
    assert u.get("/api/member_file").status_code == 403
