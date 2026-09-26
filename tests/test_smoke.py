def test_login_and_me(api):
    r = api.get("/api/me")
    assert r.status_code == 200
    assert r.get_json()["username"] == "admin"


def test_make_user(make_user):
    u, user = make_user(["member.read"])
    assert u.get("/api/member").status_code == 200
    assert u.get("/api/organization").status_code == 403
