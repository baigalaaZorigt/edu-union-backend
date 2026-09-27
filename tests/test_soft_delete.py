"""Soft delete (core/orm/soft.py) — устгасан мөр DB-д үлдэж, API-аас бүрэн алга болно."""
from sqlalchemy import text

from conftest import uniq
from core.orm import engine
from _union_helpers import make_member, make_org


def _raw(table, rid, cols="deleted_at"):
    """Soft delete-ийн шүүлтүүргүйгээр DB-ээс шууд уншина."""
    with engine().connect() as c:
        return c.execute(text(f"SELECT {cols} FROM {table} WHERE id = :i"), {"i": rid}).first()


def _set_deleted(table, where, value):
    with engine().begin() as c:
        c.execute(text(f"UPDATE {table} SET deleted_at = :v WHERE {where}"), {"v": value})


def test_user_hidden_row_kept_username_freed(api):
    name = uniq("softuser")
    body = {"username": name, "password": "Pass1234", "last_name": "А", "first_name": "Б"}
    u = api.post("/api/user", json=body).get_json()
    assert api.delete(f"/api/user/{u['id']}").get_json() == {"deleted": u["id"]}
    row = _raw("app_user", u["id"], "deleted_at, username")
    assert row.deleted_at and row.username == f"{name}~deleted~{u['id']}"
    assert api.get(f"/api/user/{u['id']}").status_code == 404
    assert u["id"] not in {x["id"] for x in api.get("/api/user").get_json()}
    assert api.delete(f"/api/user/{u['id']}").status_code == 404          # дахин устгахгүй
    again = api.post("/api/user", json=body)                               # нэр чөлөөлөгдсөн
    assert again.status_code == 201 and again.get_json()["id"] != u["id"]
    api.delete(f"/api/user/{again.get_json()['id']}")


def test_member_cascade_hides_contacts_and_education(api):
    o = make_org(api)
    m = make_member(api, o["id"])
    c = api.post("/api/contact", json={"owner_type": "member", "owner_id": m["id"],
                                       "type": "утас", "value": "99112233"}).get_json()
    e = api.post("/api/member_education", json={"member_id": m["id"]}).get_json()
    assert api.delete(f"/api/member/{m['id']}").status_code == 200
    stamps = [_raw(t, i).deleted_at for t, i in
              (("member", m["id"]), ("contact", c["id"]), ("member_education", e["id"]))]
    assert all(stamps) and len(set(stamps)) == 1                            # нэг агшинд
    assert m["id"] not in {x["id"] for x in api.get("/api/member").get_json()}
    assert api.delete(f"/api/organization/{o['id']}").status_code == 200


def test_referenced_row_blocked_with_details(api):
    o = make_org(api)
    m = make_member(api, o["id"], last_name="Холбоос", first_name="Шалгах")
    r = api.delete(f"/api/organization/{o['id']}")
    assert r.status_code == 409
    d = r.get_json()
    assert d["error"].startswith(f"«{o['name']}» (байгууллага) устгах боломжгүй: "
                                 "үүнтэй холбоотой 1 гишүүн (Холбоос Шалгах) бүртгэлтэй байна.")
    assert d["references"] == [{"table": "member", "label": "гишүүн", "count": 1,
                                "examples": ["Холбоос Шалгах"]}]
    assert _raw("organization", o["id"]).deleted_at is None                 # юу ч өөрчлөгдөөгүй
    assert api.get(f"/api/member/{m['id']}").status_code == 200
    api.delete(f"/api/member/{m['id']}")                                     # салгаад
    assert api.delete(f"/api/organization/{o['id']}").status_code == 200     # устгагдана


def test_admin_unit_cascade_checks_every_child(api):
    au1 = api.post("/api/au1", json={"code": "9" + uniq("")[-2:], "name": uniq("Аймаг ")}).get_json()
    au2 = api.post("/api/au2", json={"au2_code": au1["code"] + "01", "au2_name": "Сум",
                                     "au1_code": au1["code"]}).get_json()
    o = make_org(api, au2_code=au2["au2_code"])        # зөвхөн СУМ-ыг заана
    r = api.delete(f"/api/au1/{au1['code']}")          # каскадаар устах сум нь хаана -> 409
    assert r.status_code == 409 and "«Сум» (сум/дүүрэг)" in r.get_json()["error"]
    assert api.get(f"/api/au2/{au2['au2_code']}").status_code == 200
    api.delete(f"/api/organization/{o['id']}")
    assert api.delete(f"/api/au1/{au1['code']}").status_code == 200


def test_same_code_recreated_after_delete(api):
    o = make_org(api)
    code = o["org_code"]
    assert api.delete(f"/api/organization/{o['id']}").status_code == 200
    again = make_org(api, org_code=code)                                   # 409 биш
    assert again["org_code"] == code
    api.delete(f"/api/organization/{again['id']}")


def test_hard_flag_only_hides_form(api):
    f = api.post("/api/admin/forms", json={"title": uniq("Soft маягт"), "type": "survey"}).get_json()
    assert api.delete(f"/api/admin/forms/{f['id']}?hard=1").status_code == 200
    assert _raw("form", f["id"]).deleted_at
    assert api.get(f"/api/admin/forms/{f['id']}").status_code == 404


def test_seed_keeps_deleted_rows_hidden_and_revives_admin_grants(api):
    from core.db.seed_portal import seed_users
    from core.db.seed_ref import seed_position
    _set_deleted("position", "id = 20", "2026-01-01 00:00:00")
    _set_deleted("role_permission", "role_id = 1", "2026-01-01 00:00:00")
    try:
        seed_position()                                                    # PK зөрчилгүй
        seed_users()
        assert _raw("position", 20).deleted_at                             # сэргээгдээгүй
        assert api.get("/api/position/20").status_code == 404
        with engine().connect() as c:
            hidden = c.execute(text("SELECT COUNT(*) FROM role_permission "
                                    "WHERE role_id = 1 AND deleted_at IS NOT NULL")).scalar()
        assert hidden == 0 and api.get("/api/user").status_code == 200    # admin эрхтэй
    finally:
        _set_deleted("position", "id = 20", None)
        _set_deleted("role_permission", "role_id = 1", None)
