"""admin/users.py — эрх, дүр, хэрэглэгч, хамрах хүрээ, нэвтрэлт, self-service — хуваалцсан туслахууд (test_users_*.py ашиглана)."""

from conftest import uniq, Api


SPECIALIST = "Зөвлөх мэргэжилтэн"
DISTRICT = "01107"            # Баянгол (seed)


# ----------------------------- туслахууд -----------------------------
def _perm_id(api, code):
    return next(p["id"] for p in api.get("/api/permission").get_json() if p["code"] == code)


def _specialist_role(api):
    """Зөвлөх мэргэжилтэн дүр (нэр нь strip/casefold-оор таарна).

    role.name UNIQUE тул бусад тесттэй давхцахгүйн тулд ард нь өөр тооны зай нэмнэ.
    """
    for n in range(1, 200):
        r = api.post("/api/role", json={"name": SPECIALIST + " " * n})
        if r.status_code == 201:
            return r.get_json()["id"]
    raise AssertionError("specialist role үүсгэж чадсангүй")


def _new_user(api, role_id=None, password="Init1234", **extra):
    body = {"username": uniq("u"), "password": password,
            "last_name": "Овог", "first_name": "Нэр", **extra}
    if role_id is not None:
        body["role_id"] = role_id
    r = api.post("/api/user", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json(), body


def _login(client, username, password):
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_json()
    return Api(client, r.get_json()["token"]), r.get_json()


def _new_org(api, **extra):
    r = api.post("/api/organization", json={"name": uniq("Байгууллага"), **extra})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]
