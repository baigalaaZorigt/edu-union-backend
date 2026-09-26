"""admin/users.py — эрх, дүр, хэрэглэгч, хамрах хүрээ, нэвтрэлт, self-service — permission, role, user."""

from conftest import uniq

from _users_helpers import _login, _new_user, _perm_id


# ============================ permission ============================
def test_permission_list_and_filter(api):
    r = api.get("/api/permission")
    assert r.status_code == 200
    codes = {p["code"] for p in r.get_json()}
    assert "user.read" in codes and "dashboard.read" in codes
    r = api.get("/api/permission?resource=user")
    assert r.status_code == 200
    assert {p["action"] for p in r.get_json()} == {"create", "read", "update", "delete"}
    assert all(p["resource"] == "user" for p in r.get_json())


def test_permission_crud(api):
    code = uniq("x.") + ".read"
    r = api.post("/api/permission", json={"code": code, "name": "Тест эрх",
                                          "resource": "x", "action": "read"})
    assert r.status_code == 201
    pid = r.get_json()["id"]
    assert r.get_json()["code"] == code

    assert api.get(f"/api/permission/{pid}").get_json()["name"] == "Тест эрх"

    r = api.put(f"/api/permission/{pid}", json={"name": "Засав"})
    assert r.status_code == 200 and r.get_json() == {"updated": pid, "fields": ["name"]}
    r = api.patch(f"/api/permission/{pid}", json={"description": "тайлбар"})
    assert r.status_code == 200
    got = api.get(f"/api/permission/{pid}").get_json()
    assert got["name"] == "Засав" and got["description"] == "тайлбар"

    assert api.delete(f"/api/permission/{pid}").get_json() == {"deleted": pid}
    assert api.get(f"/api/permission/{pid}").status_code == 404
    assert api.delete(f"/api/permission/{pid}").status_code == 404
    assert api.put(f"/api/permission/{pid}", json={"name": "a"}).status_code == 404


def test_permission_validation(api):
    assert api.post("/api/permission", json={"code": "only"}).status_code == 400
    assert api.post("/api/permission", json={"code": uniq("c"), "name": "n",
                                             "action": "fly"}).status_code == 400
    assert api.post("/api/permission", json={"code": "user.read",
                                             "name": "dup"}).status_code == 409
    pid = api.post("/api/permission", json={"code": uniq("c"), "name": "n"}).get_json()["id"]
    assert api.put(f"/api/permission/{pid}", json={}).status_code == 400
    assert api.put(f"/api/permission/{pid}", json={"foo": 1}).status_code == 400
    assert api.put(f"/api/permission/{pid}", json={"action": "bad"}).status_code == 400
    assert api.put(f"/api/permission/{pid}", json={"code": "user.read"}).status_code == 409
    api.delete(f"/api/permission/{pid}")


def test_permission_get_missing(api):
    assert api.get("/api/permission/999999").status_code == 404


# =============================== role ===============================
def test_role_crud_and_permissions(api):
    p_read, p_create = _perm_id(api, "member.read"), _perm_id(api, "member.create")
    name = uniq("Дүр")
    r = api.post("/api/role", json={"name": name, "description": "d",
                                    "permission_ids": [p_read, p_read]})
    assert r.status_code == 201
    role = r.get_json()
    rid = role["id"]
    assert [p["id"] for p in role["permissions"]] == [p_read]

    got = api.get(f"/api/role/{rid}").get_json()
    assert got["name"] == name and got["user_count"] == 0
    assert any(x["id"] == rid for x in api.get("/api/role").get_json())

    # PUT: нэр + эрхийн жагсаалтыг бүхэлд нь солино
    r = api.put(f"/api/role/{rid}", json={"name": name + "2", "permission_ids": [p_create]})
    assert r.status_code == 200
    assert [p["id"] for p in r.get_json()["permissions"]] == [p_create]
    r = api.patch(f"/api/role/{rid}", json={"description": "шинэ"})
    assert r.status_code == 200 and r.get_json()["description"] == "шинэ"
    assert [p["id"] for p in r.get_json()["permissions"]] == [p_create]   # хэвээр

    # нэг нэгээр нэмэх / хасах
    r = api.post(f"/api/role/{rid}/permission", json={"permission_id": p_read})
    assert r.status_code == 201
    assert {p["id"] for p in r.get_json()["permissions"]} == {p_read, p_create}
    r = api.post(f"/api/role/{rid}/permission", json={"permission_id": p_read})
    assert r.status_code == 201 and len(r.get_json()["permissions"]) == 2   # idempotent
    r = api.delete(f"/api/role/{rid}/permission/{p_read}")
    assert r.status_code == 200
    assert r.get_json() == {"role_id": rid, "removed_permission": p_read}
    assert api.delete(f"/api/role/{rid}/permission/{p_read}").status_code == 404

    # user_count
    _new_user(api, role_id=rid)
    assert api.get(f"/api/role/{rid}").get_json()["user_count"] == 1

    assert api.delete(f"/api/role/{rid}").get_json() == {"deleted": rid}
    assert api.get(f"/api/role/{rid}").status_code == 404
    assert api.delete(f"/api/role/{rid}").status_code == 404


def test_role_validation(api):
    assert api.post("/api/role", json={}).status_code == 400
    assert api.post("/api/role", json={"name": "admin"}).status_code == 409
    assert api.post("/api/role", json={"name": uniq("r"),
                                       "permission_ids": [999999]}).status_code == 400
    rid = api.post("/api/role", json={"name": uniq("r")}).get_json()["id"]
    assert api.put(f"/api/role/{rid}", json={"name": "admin"}).status_code == 409
    assert api.put(f"/api/role/{rid}", json={"permission_ids": [999999]}).status_code == 400
    assert api.put("/api/role/999999", json={"name": "x"}).status_code == 404
    assert api.post(f"/api/role/{rid}/permission", json={}).status_code == 400
    assert api.post(f"/api/role/{rid}/permission",
                    json={"permission_id": 999999}).status_code == 400
    assert api.post("/api/role/999999/permission",
                    json={"permission_id": 1}).status_code == 404
    api.delete(f"/api/role/{rid}")


# =============================== user ===============================
def test_user_crud(api):
    rid = api.post("/api/role", json={"name": uniq("r")}).get_json()["id"]
    user, body = _new_user(api, role_id=rid, email="a@b.mn", structure_id=1)
    uid = user["id"]
    assert "password_hash" not in user and "full_name" not in user
    assert user["username"] == body["username"]
    assert user["role_name"] and user["structure_id"] == 1 and user["structure_name"]
    assert user["must_change_password"] is True       # админ үүсгэсэн -> заавал солино
    assert user["onboarding_completed"] is True       # мэргэжилтэн биш
    assert user["is_active"] == 1

    got = api.get(f"/api/user/{uid}").get_json()
    assert got["permissions"] == [] and got["scope"] is None
    assert "password_hash" not in got

    lst = api.get("/api/user").get_json()
    me = next(u for u in lst if u["id"] == uid)
    assert "scope" in me and "password_hash" not in me

    r = api.put(f"/api/user/{uid}", json={"first_name": "Шинэ", "is_active": False,
                                          "must_change_password": 0})
    assert r.status_code == 200
    assert r.get_json()["first_name"] == "Шинэ"
    assert r.get_json()["is_active"] == 0
    assert r.get_json()["must_change_password"] is False
    r = api.patch(f"/api/user/{uid}", json={"last_name": "Өөр"})
    assert r.status_code == 200 and r.get_json()["last_name"] == "Өөр"

    assert api.delete(f"/api/user/{uid}").get_json() == {"deleted": uid}
    assert api.get(f"/api/user/{uid}").status_code == 404
    assert api.delete(f"/api/user/{uid}").status_code == 404


def test_user_filters(api):
    rid = api.post("/api/role", json={"name": uniq("r")}).get_json()["id"]
    a, _ = _new_user(api, role_id=rid, structure_id=2)
    b, _ = _new_user(api, role_id=rid, structure_id=3)
    ids = {u["id"] for u in api.get(f"/api/user?role_id={rid}").get_json()}
    assert ids == {a["id"], b["id"]}
    ids = {u["id"] for u in api.get(f"/api/user?role_id={rid}&structure_id=2").get_json()}
    assert ids == {a["id"]}
    lst = api.get("/api/user?structure_id=3").get_json()
    assert b["id"] in {u["id"] for u in lst} and all(u["structure_id"] == 3 for u in lst)


def test_user_validation(api):
    assert api.post("/api/user", json={"username": uniq("u")}).status_code == 400
    assert api.post("/api/user", json={"username": uniq("u"), "password": "p",
                                       "role_id": 999999}).status_code == 400
    assert api.post("/api/user", json={"username": uniq("u"), "password": "p",
                                       "structure_id": 999999}).status_code == 400
    assert api.post("/api/user", json={"username": "admin",
                                       "password": "p"}).status_code == 409
    user, _ = _new_user(api)
    uid = user["id"]
    assert api.put(f"/api/user/{uid}", json={}).status_code == 400
    assert api.put(f"/api/user/{uid}", json={"username": "x"}).status_code == 400
    assert api.put(f"/api/user/{uid}", json={"role_id": 999999}).status_code == 400
    assert api.put(f"/api/user/{uid}", json={"structure_id": 999999}).status_code == 400
    assert api.put("/api/user/999999", json={"first_name": "x"}).status_code == 404


def test_user_password_reset_by_admin(api, client):
    user, body = _new_user(api)
    r = api.put(f"/api/user/{user['id']}", json={"password": "Reset999"})
    assert r.status_code == 200
    assert client.post("/api/login", json={"username": body["username"],
                                           "password": body["password"]}).status_code == 400
    _login(client, body["username"], "Reset999")


def test_role_code(api):
    name = uniq("кодтой дүр")
    code = uniq("R")
    r = api.post("/api/role", json={"name": name, "code": f"  {code} "})
    assert r.status_code == 201, r.get_json()
    role = r.get_json()
    assert role["code"] == code                       # зайг хасаж хадгална
    rid = role["id"]
    assert api.get(f"/api/role/{rid}").get_json()["code"] == code
    assert next(x for x in api.get("/api/role").get_json() if x["id"] == rid)["code"] == code

    # давхцал -> 409 (үүсгэх ба засах), өөрийн кодоо дахин өгөх нь зөв
    assert api.post("/api/role", json={"name": uniq("өөр"), "code": code}).status_code == 409
    other = api.post("/api/role", json={"name": uniq("өөр")}).get_json()
    assert other["code"] is None                      # code заавал биш
    assert api.patch(f"/api/role/{other['id']}", json={"code": code}).status_code == 409
    assert api.put(f"/api/role/{rid}", json={"code": code}).status_code == 200

    # буруу төрөл -> 400, хоосон мөр -> NULL
    assert api.patch(f"/api/role/{rid}", json={"code": 12}).status_code == 400
    r = api.patch(f"/api/role/{rid}", json={"code": ""})
    assert r.status_code == 200 and r.get_json()["code"] is None

    # хэрэглэгчийн хариунд role_code
    api.patch(f"/api/role/{rid}", json={"code": code})
    uid = _new_user(api, role_id=rid)[0]["id"]
    assert api.get(f"/api/user/{uid}").get_json()["role_code"] == code
    api.delete(f"/api/user/{uid}")
    api.delete(f"/api/role/{rid}")
    api.delete(f"/api/role/{other['id']}")
