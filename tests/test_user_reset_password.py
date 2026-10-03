"""POST /api/user/<id>/reset_password — нууц үг = username, дахин солиулна, токен хүчингүй."""
import time


def _login(client, username, password):
    return client.post("/api/login", json={"username": username, "password": password})


def test_super_admin_resets_anyone(api, client, make_user):
    u, user = make_user(["member.read"])
    time.sleep(1.1)                                   # iat < tokens_invalid_before болохын тулд
    r = api.post(f"/api/user/{user['id']}/reset_password")
    assert r.status_code == 200 and r.get_json() == {"status": True}
    assert u.get("/api/member").status_code == 401    # хуучин токен хүчингүй
    assert _login(client, user["username"], "Pass1234").status_code == 400
    body = _login(client, user["username"], user["username"]).get_json()
    assert body["must_change_password"] is True and "tokens_invalid_before" not in body
    row = api.get(f"/api/user/{user['id']}").get_json()
    assert row["updated_by"] == 1


def test_only_creator_or_super_admin(api, client, make_user):
    creator, c_user = make_user(["user.create", "user.update", "user.read"])
    other, _ = make_user(["user.update"])
    r = creator.post("/api/user", json={"username": "88110011", "password": "x1234567"})
    assert r.status_code == 201 and r.get_json()["created_by"] == c_user["id"]
    uid = r.get_json()["id"]
    assert other.post(f"/api/user/{uid}/reset_password").status_code == 403
    assert _login(client, "88110011", "x1234567").status_code == 200      # өөрчлөгдөөгүй
    assert creator.post(f"/api/user/{uid}/reset_password").status_code == 200
    assert _login(client, "88110011", "88110011").status_code == 200
    # бүртгэгч нь өөрийгөө үүсгэсэн админы бүртгэлийг сэргээж чадахгүй
    assert creator.post("/api/user/1/reset_password").status_code == 403
    api.delete(f"/api/user/{uid}")


def test_needs_user_update_and_404(api, make_user):
    u, user = make_user(["user.create", "user.read"])
    assert u.post(f"/api/user/{user['id']}/reset_password").status_code == 403
    assert api.post("/api/user/99999999/reset_password").status_code == 404
