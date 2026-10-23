"""member_status лавлах + member.status_id (Alembic 0010, member_status спек)."""
import importlib.util
import os

from conftest import MEMBER_REQ, uniq


def _match():
    """alembic/versions нь багц биш — migration-ийн _match-ийг файлаас нь ачаална."""
    path = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions",
                        "0010_member_status.py")
    spec = importlib.util.spec_from_file_location("m0010", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._match


def _org(api):
    r = api.post("/api/organization", json={"name": uniq("Статус сургууль")})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _member(api, **kw):
    body = {**MEMBER_REQ, "organization_id": _org(api), "first_name": uniq("Бат")}
    body.update(kw)
    return api.post("/api/member", json=body)


def test_seeded_statuses(api):
    rows = api.get("/api/member_status").get_json()
    names = {r["id"]: r["name"] for r in rows}
    assert names[1] == "Гишүүн" and names[2] == "Дарга"
    assert names[3] == "Тэргүүлэгч" and names[4] == "Сонгуульт"
    assert rows[0]["code"] == "01"


def test_member_status_id_fills_status(api):
    r = _member(api, status_id=3, status=None)
    assert r.status_code == 201, r.get_json()
    m = r.get_json()
    assert (m["status_id"], m["status_name"], m["status"]) == (3, "Тэргүүлэгч", "Тэргүүлэгч")
    assert m["member_status"] is None or isinstance(m["member_status"], str)
    got = api.get(f"/api/member/{m['id']}").get_json()
    assert got["status_name"] == "Тэргүүлэгч"
    listed = api.get(f"/api/member?organization_id={m['organization_id']}").get_json()
    assert listed[0]["status_id"] == 3

    r = api.patch(f"/api/member/{m['id']}", json={"status_id": "2"})
    assert r.status_code == 200
    assert set(r.get_json()["fields"]) == {"status_id", "status"}
    got = api.get(f"/api/member/{m['id']}").get_json()
    assert (got["status_id"], got["status"]) == (2, "Дарга")


def test_member_bad_status_id_400(api):
    assert _member(api, status_id=999999).status_code == 400
    m = _member(api).get_json()
    assert api.put(f"/api/member/{m['id']}", json={"status_id": 999999}).status_code == 400


def test_legacy_status_text_is_matched_case_insensitively(api):
    m = _member(api, status="  гишүүн ").get_json()
    assert (m["status_id"], m["status"], m["status_name"]) == (1, "Гишүүн", "Гишүүн")
    m = _member(api, status="Багш").get_json()
    assert (m["status_id"], m["status"], m["status_name"]) == (None, "Багш", None)


def test_status_required_by_text_or_id(api):
    body = {k: v for k, v in MEMBER_REQ.items() if k != "status"}
    r = api.post("/api/member", json={**body, "organization_id": _org(api)})
    assert r.status_code == 400
    r = api.post("/api/member", json={**body, "organization_id": _org(api), "status_id": 1})
    assert r.status_code == 201 and r.get_json()["status"] == "Гишүүн"


def test_delete_used_status_is_409(api):
    st = api.post("/api/member_status", json={"code": uniq("s"), "name": uniq("Статус ")}).get_json()
    m = _member(api, status_id=st["id"]).get_json()
    r = api.delete(f"/api/member_status/{st['id']}")
    assert r.status_code == 409
    assert "(гишүүний статус) устгах боломжгүй" in r.get_json()["error"]
    assert r.get_json()["references"][0]["count"] == 1
    assert api.patch(f"/api/member/{m['id']}", json={"status_id": None}).status_code == 200
    assert api.delete(f"/api/member_status/{st['id']}").status_code == 200


def test_name_unique_and_length(api):
    name = uniq("Давхар ")
    assert api.post("/api/member_status", json={"name": name}).status_code == 201
    assert api.post("/api/member_status", json={"name": name.upper()}).status_code == 409
    assert api.post("/api/member_status", json={"name": "x" * 151}).status_code == 400
    assert api.post("/api/member_status", json={"name": uniq("n"), "code": "1" * 21}).status_code == 400
    r = api.post("/api/member_status", json={"name": uniq("Өөр ")})
    assert api.put(f"/api/member_status/{r.get_json()['id']}", json={"name": name}).status_code == 409


def test_migration_mapping():
    match = _match()
    assert match("гишүүн") == match("Гишүүн") == "Гишүүн"
    assert match("Тэргүүлэгч, хорооны дарга") == "Тэргүүлэгч"
    for v in ("Зөвлөлийн дарга", "Бүлгийн дарга", "ҮЭ-ийн бүлгийн дарга", "дарга",
              "ҮЭ-ийн хорооны дарга"):
        assert match(v) == "Дарга", v
    for v in ("Багш", "0014", "Боловсрол", "", None, "идэвхтэй"):
        assert match(v) is None, v
