"""Гүйцэтгэл ба нэвтрэлтийн хамгаалалт: N+1 арилсан, brute-force хязгаар, hash шинэчлэлт."""
from werkzeug.security import generate_password_hash

import admin.users.login_guard as guard
from core import db
from conftest import uniq


def _count_queries(client_call):
    """Хүсэлтийн үед ажилласан SQL тоо (SQLite trace)."""
    n = {"q": 0}
    orig = db.get_db

    def counting():
        conn = orig()
        conn.set_trace_callback(lambda _s: n.__setitem__("q", n["q"] + 1))
        return conn
    import sys
    mods = [m for m in list(sys.modules.values()) if getattr(m, "get_db", None) is orig]
    for m in mods:
        m.get_db = counting
    try:
        r = client_call()
    finally:
        for m in mods:
            m.get_db = orig
    return r, n["q"]


# ================================ N+1 ================================
def test_org_list_query_count_is_constant(api):
    _, before = _count_queries(lambda: api.get("/api/organization"))
    for _ in range(5):
        api.post("/api/organization", json={"name": uniq("N1 сургууль"),
                                            "org_code": f"{int(uniq('')) % 900 + 100:03d}"})
    r, after = _count_queries(lambda: api.get("/api/organization"))
    assert r.status_code == 200
    assert after == before                      # байгууллага нэмэгдэхэд query өсөхгүй


def test_org_stats_values_unchanged(api):
    org = api.post("/api/organization", json={"name": uniq("Статистик"),
                                              "org_code": f"{int(uniq('')) % 900 + 100:03d}"}).get_json()
    for g, bd in (("эм", "2000-01-01"), ("эм", "1970-01-01"), ("эр", "2001-05-05"), ("эр", None)):
        api.post("/api/member", json={"organization_id": org["id"], "last_name": "О",
                                      "first_name": "Н", "gender": g, "birth_date": bd})
    listed = next(o for o in api.get("/api/organization").get_json() if o["id"] == org["id"])
    one = api.get(f"/api/organization/{org['id']}").get_json()
    for d in (listed, one):
        assert (d["total_members"], d["female_members"], d["under35_members"]) == (4, 2, 2)
    empty = api.post("/api/organization", json={"name": uniq("Хоосон"),
                                                "org_code": f"{int(uniq('')) % 900 + 100:03d}"}).get_json()
    got = next(o for o in api.get("/api/organization").get_json() if o["id"] == empty["id"])
    assert got["total_members"] == 0 and got["under35_members"] == 0


def test_role_list_query_count_is_constant(api):
    _, before = _count_queries(lambda: api.get("/api/role"))
    ids = [api.post("/api/role", json={"name": uniq("N1 дүр")}).get_json()["id"] for _ in range(4)]
    r, after = _count_queries(lambda: api.get("/api/role"))
    assert after == before
    by_id = {x["id"]: x for x in r.get_json()}
    assert all(by_id[i]["permissions"] == [] for i in ids)
    assert len(by_id[1]["permissions"]) > 100            # admin бүх эрхтэй хэвээр
    for i in ids:
        api.delete(f"/api/role/{i}")


# ============================ brute-force ============================
def _login(client, user, pw, ip="203.0.113.10"):
    return client.post("/api/login", json={"username": user, "password": pw},
                       headers={"X-Real-IP": ip})


def test_lockout_per_username_and_ip(client, make_user):
    _, user = make_user([], password="Right1234")
    name = user["username"]
    for _ in range(guard.MAX_PER_USER_IP):
        assert _login(client, name, "wrong").status_code == 400
    r = _login(client, name, "Right1234")                # зөв нууц үг ч түгжигдсэн
    assert r.status_code == 429 and "минутын дараа" in r.get_json()["error"]
    # өөр IP-ээс тухайн хэрэглэгч нэвтэрч чадна (гадны хүн admin-ыг түгжиж чадахгүй)
    assert _login(client, name, "Right1234", ip="198.51.100.20").status_code == 200


def test_success_resets_counter(client, make_user):
    _, user = make_user([], password="Right1234")
    name = user["username"]
    for _ in range(guard.MAX_PER_USER_IP - 1):
        _login(client, name, "wrong")
    assert _login(client, name, "Right1234").status_code == 200
    for _ in range(guard.MAX_PER_USER_IP - 1):
        _login(client, name, "wrong")
    assert _login(client, name, "Right1234").status_code == 200


def test_ip_limit_across_usernames(client, monkeypatch):
    monkeypatch.setattr(guard, "MAX_PER_IP", 3)
    for i in range(3):
        assert _login(client, f"байхгүй{i}", "x", ip="192.0.2.77").status_code == 400
    assert _login(client, "admin", "admin123", ip="192.0.2.77").status_code == 429
    assert _login(client, "admin", "admin123", ip="192.0.2.78").status_code == 200


def test_window_expiry(client, make_user):
    _, user = make_user([], password="Right1234")
    name = user["username"]
    for _ in range(guard.MAX_PER_USER_IP):
        _login(client, name, "wrong")
    assert _login(client, name, "Right1234").status_code == 429
    conn = db.get_db()
    conn.execute("UPDATE login_attempt SET created_at='2000-01-01 00:00:00'")
    conn.commit()
    conn.close()
    assert _login(client, name, "Right1234").status_code == 200


# ============================== hash ==============================
def test_old_hash_upgraded_on_login(client, make_user):
    _, user = make_user([], password="Right1234")
    conn = db.get_db()
    conn.execute("UPDATE app_user SET password_hash=? WHERE id=?",
                 (generate_password_hash("Right1234", method="pbkdf2:sha256:1000000"), user["id"]))
    conn.commit()
    assert _login(client, user["username"], "Right1234").status_code == 200
    h = conn.execute("SELECT password_hash FROM app_user WHERE id=?", (user["id"],)).fetchone()[0]
    conn.close()
    assert h.startswith("pbkdf2:sha256:600000$")
    assert _login(client, user["username"], "Right1234").status_code == 200   # шинэ hash ажиллана


def test_new_users_use_600k(api, make_user):
    _, user = make_user([])
    conn = db.get_db()
    h = conn.execute("SELECT password_hash FROM app_user WHERE id=?", (user["id"],)).fetchone()[0]
    conn.close()
    assert h.startswith("pbkdf2:sha256:600000$")
