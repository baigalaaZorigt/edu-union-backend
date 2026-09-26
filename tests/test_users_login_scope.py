"""admin/users.py — эрх, дүр, хэрэглэгч, хамрах хүрээ, нэвтрэлт, self-service — login, self-service, user_scope."""

import pytest

from conftest import uniq, Api

from _users_helpers import DISTRICT, _login, _new_org, _new_user, _perm_id, _specialist_role


# ============================== login ==============================
def test_login_shape(api, client):
    rid = api.post("/api/role", json={"name": uniq("r"),
                                      "permission_ids": [_perm_id(api, "member.read")]}
                   ).get_json()["id"]
    user, body = _new_user(api, role_id=rid)
    _, out = _login(client, body["username"], body["password"])
    assert out["token"] and out["id"] == user["id"]
    assert "password_hash" not in out
    assert [p["code"] for p in out["permissions"]] == ["member.read"]
    assert out["scope"] is None
    assert out["must_change_password"] is True and out["onboarding_completed"] is True


def test_login_rejections(api, client):
    assert client.post("/api/login", json={}).status_code == 400
    assert client.post("/api/login", json={"username": "admin"}).status_code == 400
    assert client.post("/api/login", json={"username": "admin",
                                           "password": "wrong"}).status_code == 400
    assert client.post("/api/login", json={"username": "nobody-xyz",
                                           "password": "x"}).status_code == 400
    user, body = _new_user(api, is_active=False)
    r = client.post("/api/login", json={"username": body["username"],
                                        "password": body["password"]})
    assert r.status_code == 400 and "идэвхгүй" in r.get_json()["error"]


def test_auth_required(anon, api):
    for url in ("/api/user", "/api/role", "/api/permission", "/api/me",
                "/api/me/scope", "/api/me/organizations"):
        assert anon.get(url).status_code == 401, url
    assert anon.post("/api/change_password", json={}).status_code == 401
    assert anon.post("/api/me/onboarding/complete").status_code == 401
    bad = Api(anon.client, "not-a-jwt")
    assert bad.get("/api/user").status_code == 401


def test_permissions_enforced(make_user):
    u, _ = make_user(["user.read"])
    assert u.get("/api/user").status_code == 200
    assert u.post("/api/user", json={"username": "x", "password": "y"}).status_code == 403
    assert u.get("/api/role").status_code == 403
    assert u.get("/api/permission").status_code == 403
    assert u.get("/api/user/1/scope").status_code == 200     # user.read хүрнэ
    assert u.put("/api/user/1/scope", json={}).status_code == 403


# ========================= self-service =========================
def test_change_password(api, client):
    user, body = _new_user(api)
    me, _ = _login(client, body["username"], body["password"])
    assert me.get("/api/me").get_json()["must_change_password"] is True

    assert me.post("/api/change_password", json={}).status_code == 400
    assert me.post("/api/change_password",
                   json={"current_password": "x"}).status_code == 400
    r = me.post("/api/change_password", json={"current_password": "wrong",
                                              "new_password": "New12345"})
    assert r.status_code == 422 and "error" in r.get_json()

    r = me.post("/api/change_password", json={"current_password": body["password"],
                                              "new_password": "New12345"})
    assert r.status_code == 200 and r.get_json() == {"status": True}
    assert me.get("/api/me").get_json()["must_change_password"] is False
    assert client.post("/api/login", json={"username": body["username"],
                                           "password": body["password"]}).status_code == 400
    _login(client, body["username"], "New12345")


def test_me_role_less_user(api, client):
    """Дүргүй хэрэглэгч ч өөрийн маршрутуудыг ашиглана (эрх шаардахгүй)."""
    user, body = _new_user(api)
    me, _ = _login(client, body["username"], body["password"])
    r = me.get("/api/me")
    assert r.status_code == 200
    out = r.get_json()
    assert out["id"] == user["id"] and out["permissions"] == [] and out["scope"] is None
    assert "token" not in out and "password_hash" not in out
    assert me.get("/api/me/scope").status_code == 200
    assert me.get("/api/me/scope").get_json() is None
    assert me.get("/api/user").status_code == 403


def test_specialist_onboarding_flow(api, client):
    rid = _specialist_role(api)
    user, body = _new_user(api, role_id=rid)
    assert user["onboarding_completed"] is False
    me, login = _login(client, body["username"], body["password"])
    assert login["onboarding_completed"] is False and login["must_change_password"] is True

    r = me.post("/api/me/onboarding/complete")
    assert r.status_code == 200
    first = r.get_json()
    assert first["status"] is True and first["onboarding_completed"] is True
    assert first["onboarding_completed_at"]
    again = me.post("/api/me/onboarding/complete").get_json()
    assert again["onboarding_completed_at"] == first["onboarding_completed_at"]   # COALESCE
    assert me.get("/api/me").get_json()["onboarding_completed"] is True
    assert api.get(f"/api/user/{user['id']}").get_json()["onboarding_completed"] is True


def test_specialist_role_name_case_insensitive(api):
    rid = None
    for n in range(1, 200):
        r = api.post("/api/role", json={"name": "  зӨвлӨх МЭРГЭЖИЛТЭН" + " " * n})
        if r.status_code == 201:
            rid = r.get_json()["id"]
            break
    user, _ = _new_user(api, role_id=rid)
    assert user["onboarding_completed"] is False


# ============================ user_scope ============================
def test_scope_district_crud(api):
    user, _ = _new_user(api)
    uid = user["id"]
    assert api.get(f"/api/user/{uid}/scope").get_json() is None
    assert api.delete(f"/api/user/{uid}/scope").status_code == 404

    r = api.put(f"/api/user/{uid}/scope", json={"school_type": "general",
                                                "district_au2_code": DISTRICT})
    assert r.status_code == 200
    s = r.get_json()
    assert s["school_type"] == "general" and s["district_au2_code"] == DISTRICT
    assert s["organization_ids"] == [] and s["organization_id"] is None

    assert api.get(f"/api/user/{uid}/scope").get_json()["school_type"] == "general"
    assert api.get(f"/api/user/{uid}").get_json()["scope"]["district_au2_code"] == DISTRICT
    lst = api.get("/api/user").get_json()
    assert next(u for u in lst if u["id"] == uid)["scope"]["school_type"] == "general"

    # PATCH merges: зөвхөн school_type солино, дүүрэг хэвээр
    r = api.patch(f"/api/user/{uid}/scope", json={"school_type": "preschool"})
    assert r.status_code == 200
    assert r.get_json()["school_type"] == "preschool"
    assert r.get_json()["district_au2_code"] == DISTRICT

    # PUT overwrites: илгээгээгүй талбар хоосорно
    oid = _new_org(api)
    r = api.put(f"/api/user/{uid}/scope", json={"organization_id": oid})
    assert r.status_code == 200
    s = r.get_json()
    assert s["organization_id"] == oid and s["school_type"] is None
    assert s["district_au2_code"] is None

    assert api.delete(f"/api/user/{uid}/scope").get_json() == {"deleted": uid}
    assert api.get(f"/api/user/{uid}/scope").get_json() is None


def test_scope_rural(api):
    user, _ = _new_user(api)
    o1, o2 = _new_org(api), _new_org(api)
    r = api.put(f"/api/user/{user['id']}/scope",
                json={"school_type": "rural", "organization_ids": [o1, str(o2)]})
    assert r.status_code == 200
    assert r.get_json()["organization_ids"] == [o1, o2]     # always a list of ints
    r = api.put(f"/api/user/{user['id']}/scope",
                json={"school_type": "rural", "organization_ids": None})
    assert r.status_code == 200 and r.get_json()["organization_ids"] == []


@pytest.mark.parametrize("body", [
    {"school_type": "space"},
    {"school_type": "general"},                                   # дүүрэг заавал
    {"school_type": "general", "district_au2_code": DISTRICT, "organization_ids": [1]},
    {"school_type": "rural", "district_au2_code": DISTRICT},
    {"school_type": "rural", "organization_ids": "1,2"},
    {"school_type": "rural", "organization_ids": ["abc"]},
    {"school_type": "rural", "organization_ids": [999999]},
    {"school_type": "general", "district_au2_code": "99999"},
    {"organization_id": 999999},
])
def test_scope_validation(api, body):
    user, _ = _new_user(api)
    r = api.put(f"/api/user/{user['id']}/scope", json=body)
    assert r.status_code == 400, (body, r.get_json())


def test_scope_missing_user_and_body(api):
    assert api.get("/api/user/999999/scope").status_code == 404
    assert api.put("/api/user/999999/scope", json={"school_type": None}).status_code == 404
    assert api.delete("/api/user/999999/scope").status_code == 404
    user, _ = _new_user(api)
    r = api.put(f"/api/user/{user['id']}/scope", data="nope",
                headers={"Content-Type": "text/plain"})
    assert r.status_code == 400


def test_role_change_deletes_scope(api):
    r1 = api.post("/api/role", json={"name": uniq("r")}).get_json()["id"]
    r2 = api.post("/api/role", json={"name": uniq("r")}).get_json()["id"]
    user, _ = _new_user(api, role_id=r1)
    uid = user["id"]
    api.put(f"/api/user/{uid}/scope", json={"school_type": "general",
                                            "district_au2_code": DISTRICT})
    # ижил дүр — хүрээ хэвээр
    api.put(f"/api/user/{uid}", json={"role_id": r1})
    assert api.get(f"/api/user/{uid}/scope").get_json() is not None
    # өөр дүр — хүрээ устана
    api.put(f"/api/user/{uid}", json={"role_id": r2})
    assert api.get(f"/api/user/{uid}/scope").get_json() is None


def test_user_delete_cascades_scope(api):
    user, _ = _new_user(api)
    uid = user["id"]
    api.put(f"/api/user/{uid}/scope", json={"school_type": "rural", "organization_ids": []})
    api.delete(f"/api/user/{uid}")
    assert api.get(f"/api/user/{uid}/scope").status_code == 404


def test_me_scope_and_organizations(api, client):
    perms = [_perm_id(api, c) for c in ("organization.read", "member.read")]
    rid = _specialist_role(api)
    api.put(f"/api/role/{rid}", json={"permission_ids": perms})
    user, body = _new_user(api, role_id=rid)
    me, _ = _login(client, body["username"], body["password"])

    o_in = _new_org(api, contact_name="Бат", phone1="99112233")
    o_out = _new_org(api)

    assert me.get("/api/me/scope").get_json() is None
    r = me.put("/api/me/scope", json={"school_type": "rural", "organization_ids": [o_in]})
    assert r.status_code == 200 and r.get_json()["organization_ids"] == [o_in]
    assert api.get(f"/api/user/{user['id']}/scope").get_json()["organization_ids"] == [o_in]
    r = me.patch("/api/me/scope", json={"organization_ids": [o_in]})
    assert r.status_code == 200 and r.get_json()["school_type"] == "rural"
    assert me.put("/api/me/scope", json={"school_type": "bad"}).status_code == 400

    r = me.get("/api/me/organizations")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert [o["id"] for o in items] == [o_in]
    assert set(items[0]) == {"id", "name", "contact_name", "phone1", "phone2", "email"}
    assert items[0]["contact_name"] == "Бат"

    # хүрээ бодитоор хэрэгжинэ
    org_ids = {o["id"] for o in me.get("/api/organization").get_json()}
    assert o_in in org_ids and o_out not in org_ids
    assert me.get(f"/api/organization/{o_out}").status_code == 403

    # хоосон ХОН хүрээ -> хоосон (бүгд биш)
    me.put("/api/me/scope", json={"school_type": "rural", "organization_ids": []})
    assert me.get("/api/me/organizations").get_json()["items"] == []


def test_me_organizations_admin_sees_all(api):
    oid = _new_org(api)
    items = api.get("/api/me/organizations").get_json()["items"]
    assert oid in {o["id"] for o in items}
