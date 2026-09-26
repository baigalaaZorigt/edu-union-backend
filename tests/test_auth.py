"""core/auth.py + run.py: нэвтрэлт (401), эрх (403), нээлттэй замууд, CORS, JSON алдаа."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from core import auth
from conftest import uniq, PNG_BYTES


# ---------------------------------------------------------------- /api/login
def test_login_ok_returns_token_and_permissions(anon):
    r = anon.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["token"] and body["username"] == "admin"
    assert "password_hash" not in body
    assert "member.read" in {p["code"] for p in body["permissions"]}
    claims = jwt.decode(body["token"], auth.SECRET_KEY, algorithms=["HS256"])
    assert claims["sub"] == str(body["id"]) and claims["exp"] > claims["iat"]


def test_login_wrong_password_400(anon):
    r = anon.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_login_unknown_user_400(anon):
    r = anon.post("/api/login", json={"username": uniq("nobody"), "password": "x"})
    assert r.status_code == 400


def test_login_missing_fields_400(anon):
    assert anon.post("/api/login", json={"username": "admin"}).status_code == 400
    assert anon.post("/api/login").status_code == 400


def test_login_inactive_user_400_and_token_revoked(api, anon, make_user):
    u, user = make_user(["member.read"])
    assert u.get("/api/member").status_code == 200
    r = api.patch(f"/api/user/{user['id']}", json={"is_active": 0})
    assert r.status_code == 200, r.get_json()
    r = anon.post("/api/login", json={"username": user["username"], "password": "Pass1234"})
    assert r.status_code == 400
    # Идэвхгүй болсон хэрэглэгчийн өмнөх токен ч ажиллахгүй
    assert u.get("/api/member").status_code == 401


# ---------------------------------------------------------------- 401
def test_no_token_401(anon):
    r = anon.get("/api/member")
    assert r.status_code == 401
    assert "error" in r.get_json()


def test_non_bearer_header_401(client):
    r = client.get("/api/member", headers={"Authorization": "Token abc"})
    assert r.status_code == 401


def test_garbage_token_401(client):
    r = client.get("/api/member", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_wrong_signature_401(client):
    tok = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                     "another-secret-key-that-is-long-enough-32b", algorithm="HS256")
    r = client.get("/api/member", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_expired_token_401(client):
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    tok = jwt.encode({"sub": "1", "iat": past - timedelta(hours=12), "exp": past},
                     auth.SECRET_KEY, algorithm="HS256")
    r = client.get("/api/member", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401
    assert "хугацаа" in r.get_json()["error"]


def test_token_for_missing_user_401(client):
    tok = auth.make_token(999999)
    assert client.get("/api/member",
                      headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_token_without_sub_401(client):
    tok = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                     auth.SECRET_KEY, algorithm="HS256")
    assert client.get("/api/member",
                      headers={"Authorization": f"Bearer {tok}"}).status_code == 401


# ---------------------------------------------------------------- 403 / derived permissions
def test_permission_is_per_action(make_user):
    u, _ = make_user(["admin_unit.read"])
    assert u.get("/api/au1").status_code == 200
    assert u.get("/api/au2").status_code == 200        # au1/au2/au3 -> admin_unit
    r = u.post("/api/au1", json={"code": uniq("A"), "name": "x"})
    assert r.status_code == 403
    assert "admin_unit.create" in r.get_json()["error"]
    assert u.put("/api/au1/011", json={"name": "x"}).status_code == 403
    assert u.patch("/api/au1/011", json={"name": "x"}).status_code == 403
    assert u.delete("/api/au1/011").status_code == 403
    assert u.get("/api/member").status_code == 403


def test_update_permission_covers_put_and_patch(api, make_user):
    code = uniq("A")
    assert api.post("/api/au1", json={"code": code, "name": "x"}).status_code == 201
    u, _ = make_user(["admin_unit.update"])
    assert u.put(f"/api/au1/{code}", json={"name": "y"}).status_code == 200
    assert u.patch(f"/api/au1/{code}", json={"name": "z"}).status_code == 200
    assert u.get(f"/api/au1/{code}").status_code == 403
    assert api.delete(f"/api/au1/{code}").status_code == 200


def test_role_less_user_403_on_resources(make_user):
    u, _ = make_user([])
    assert u.get("/api/au1").status_code == 403
    assert u.get("/api/user").status_code == 403


def test_self_paths_need_token_but_no_permission(make_user, anon):
    u, user = make_user([])
    r = u.get("/api/me")
    assert r.status_code == 200 and r.get_json()["id"] == user["id"]
    assert u.get("/api/me/scope").status_code in (200, 404)
    assert u.get("/api/notifications").status_code == 200
    assert anon.get("/api/me").status_code == 401
    assert anon.get("/api/notifications").status_code == 401


@pytest.mark.parametrize("method,path,expected", [
    ("GET", "/api/au1", "admin_unit.read"),
    ("POST", "/api/au3", "admin_unit.create"),
    ("PUT", "/api/organization/5", "organization.update"),
    ("PATCH", "/api/organization/5", "organization.update"),
    ("DELETE", "/api/member/5", "member.delete"),
    ("GET", "/api/admin/forms", "form.read"),
    ("POST", "/api/admin/forms/1/publish", "form.update"),
    ("POST", "/api/admin/forms/1/close", "form.update"),
    ("GET", "/api/admin/forms/1/questions/9/answers", "form_result.read"),
    ("POST", "/api/admin/forms/1/questions", "form_question.create"),
    ("POST", "/api/admin/forms/1/questions/reorder", "form_question.update"),
    ("DELETE", "/api/admin/options/3", "form_option.delete"),
    ("POST", "/api/admin/forms/1/document", "form_document.create"),
    ("GET", "/api/admin/news/41/blocks", "news_block.read"),
    ("PUT", "/api/admin/news_blocks/2", "news_block.update"),
    ("GET", "/api/admin/suggestions", "suggestion.read"),
    ("DELETE", "/api/admin/complaints/1", "complaint.delete"),
    ("GET", "/api/admin/notifications", "notification.read"),
    ("PUT", "/api/menu/reorder", "menu.update"),
])
def test_required_permission_mapping(app, method, path, expected):
    with app.test_request_context(path, method=method):
        assert auth._required_permission() == expected


def test_every_required_permission_is_seeded(app, api):
    """Бүх маршрутын шаардах эрх нь seed-лэгдсэн эрхийн жагсаалтад байх ёстой."""
    codes = {p["code"] for p in api.get("/api/permission").get_json()}
    missing = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        path = rule.rule
        for conv in ("<int:", "<path:", "<"):
            while conv in path:
                s = path.index(conv)
                e = path.index(">", s)
                path = path[:s] + "1" + path[e + 1:]
        if path in auth.PUBLIC_PATHS or path.startswith(auth.PUBLIC_PREFIXES) \
                or path in auth.SELF_PATHS or path.startswith(auth.SELF_PREFIXES):
            continue
        for m in rule.methods - {"HEAD", "OPTIONS"}:
            with app.test_request_context(path, method=m):
                need = auth._required_permission()
            if need and need not in codes:
                missing.add((m, rule.rule, need))
    assert not missing, sorted(missing)


# ---------------------------------------------------------------- public prefixes
def test_public_endpoints_without_token(anon):
    assert anon.get("/api/portal/forms").status_code == 200
    assert anon.get("/api/portal/news").status_code == 200
    assert anon.get("/api/public/portal_settings").status_code == 200
    assert anon.get("/api/portal/portal_settings").status_code == 200


def test_public_prefix_ignores_bad_token(client):
    r = client.get("/api/portal/news", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 200


def test_uploads_served_without_token(api, anon):
    r = api.post("/api/upload", data={"file": (__import__("io").BytesIO(PNG_BYTES), "a.png")},
                 content_type="multipart/form-data")
    assert r.status_code in (200, 201), r.get_json()
    url = r.get_json()["url"]
    assert url.startswith("/uploads/content/")
    got = anon.get(url)
    assert got.status_code == 200
    assert got.data == PNG_BYTES
    # Байхгүй файл — 401 биш 404
    assert anon.get("/uploads/content/nope.png").status_code == 404
    assert anon.get("/uploads/form/nope.pdf").status_code == 404


def test_upload_itself_needs_token(anon):
    r = anon.post("/api/upload", data={"file": (__import__("io").BytesIO(PNG_BYTES), "a.png")},
                  content_type="multipart/form-data")
    assert r.status_code == 401


# ---------------------------------------------------------------- CORS / OPTIONS
def test_options_preflight_without_token(client):
    r = client.options("/api/member", headers={
        "Origin": "https://fmesu.mn",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type"})
    assert r.status_code in (200, 204)
    assert r.headers.get("Access-Control-Allow-Origin") == "*"
    assert "PATCH" in r.headers["Access-Control-Allow-Methods"]
    assert "Authorization" in r.headers["Access-Control-Allow-Headers"]


def test_cors_header_on_error_response(client):
    r = client.get("/api/member", headers={"Origin": "https://x.example"})
    assert r.status_code == 401
    assert r.headers.get("Access-Control-Allow-Origin") == "*"


def test_no_cors_header_without_origin(api):
    r = api.get("/api/au1")
    assert "Access-Control-Allow-Origin" not in r.headers


def test_cors_allowlist(api, monkeypatch):
    import run
    monkeypatch.setattr(run, "CORS_ORIGINS", ["https://fmesu.mn"])
    ok = api.get("/api/au1", headers={"Origin": "https://fmesu.mn"})
    assert ok.headers.get("Access-Control-Allow-Origin") == "https://fmesu.mn"
    assert ok.headers.get("Vary") == "Origin"
    bad = api.get("/api/au1", headers={"Origin": "https://evil.example"})
    assert bad.status_code == 200
    assert "Access-Control-Allow-Origin" not in bad.headers


# ---------------------------------------------------------------- JSON error handlers
def test_unknown_url_json_404(api, anon):
    # Токенгүй бол эхлээд 401 (зам байгаа эсэхээс үл хамаарна)
    assert anon.get("/nope/at/all").status_code == 401
    r = api.get("/nope/at/all")
    assert r.status_code == 404
    assert r.is_json and "error" in r.get_json()
    r = api.get("/api/portal/definitely_not_here")
    assert r.status_code == 404 and r.is_json


def test_wrong_method_json_405(api):
    r = api.post("/api/au1/011", json={"name": "x"})
    assert r.status_code == 405
    assert r.is_json
    assert "GET" in r.get_json()["error"]


def test_wrong_method_on_login_405(anon):
    r = anon.get("/api/login")
    assert r.status_code == 405
    assert r.is_json


def test_unicode_not_escaped(api):
    r = api.get("/api/au1/011")
    assert "\\u" not in r.get_data(as_text=True)
