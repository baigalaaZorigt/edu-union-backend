"""Хэрэглэгч үүсгэснээрээ харагдана: Super Admin бүгдийг, бусад нь зөвхөн өөрийн бүртгэснийг."""
from conftest import uniq

PERMS = ["user.read", "user.create", "user.update", "user.delete"]


def _create(u, **extra):
    r = u.post("/api/user", json={"username": uniq("u"), "password": "Pass1234", **extra})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_list_shows_only_own_users(api, make_user):
    a, a_user = make_user(PERMS)
    b, b_user = make_user(PERMS)
    mine, theirs = _create(a), _create(b)
    ids = {u["id"] for u in a.get("/api/user").get_json()}
    assert ids == {mine["id"]}                                  # өөрөө ч, бусдынх ч алга
    assert a.get("/api/user?page=1").get_json()["total"] == 1
    admin_ids = {u["id"] for u in api.get("/api/user").get_json()}
    assert {mine["id"], theirs["id"], a_user["id"], b_user["id"], 1} <= admin_ids
    for uid in (mine["id"], theirs["id"]):
        api.delete(f"/api/user/{uid}")


def test_foreign_user_is_403_everywhere(api, make_user):
    a, _ = make_user(PERMS)
    b, _ = make_user(PERMS)
    mine, theirs = _create(a), _create(b)
    t = f"/api/user/{theirs['id']}"
    assert a.get(t).status_code == 403
    assert a.patch(t, json={"first_name": "x"}).status_code == 403
    assert a.get(t + "/scope").status_code == 403
    assert a.put(t + "/scope", json={}).status_code == 403
    assert a.delete(t + "/scope").status_code == 403
    assert a.post(t + "/reset_password").status_code == 403
    assert a.delete(t).status_code == 403
    assert a.get("/api/user/1").status_code == 403
    assert a.get("/api/user/99999999").status_code == 404
    m = f"/api/user/{mine['id']}"
    assert a.get(m).get_json()["created_by"] is not None
    assert a.patch(m, json={"first_name": "Шинэ"}).status_code == 200
    assert a.put(m + "/scope", json={"school_type": None}).status_code == 200
    assert a.post(m + "/reset_password").status_code == 200
    assert a.delete(m).status_code == 200
    api.delete(t)


def test_super_admin_role_code_sees_all(api, make_user):
    sup, sup_user = make_user(PERMS)
    other, _ = make_user(PERMS)
    theirs = _create(other)
    assert sup.get(f"/api/user/{theirs['id']}").status_code == 403
    assert api.patch(f"/api/role/{sup_user['role_id']}", json={"code": "1"}).status_code == 200
    assert sup.get(f"/api/user/{theirs['id']}").status_code == 200
    assert theirs["id"] in {u["id"] for u in sup.get("/api/user").get_json()}
    assert sup.post(f"/api/user/{theirs['id']}/reset_password").status_code == 200
    api.patch(f"/api/role/{sup_user['role_id']}", json={"code": None})
    api.delete(f"/api/user/{theirs['id']}")
