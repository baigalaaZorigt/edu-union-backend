"""Мэдэгдэл — /api/admin/notifications (илгээх тал) ба /api/notifications (🔔 inbox)."""
import pytest

from conftest import uniq

PAST = "2020-01-01 00:00:00"
FUTURE = "2099-01-01 00:00:00"


def _notify(api, **kw):
    body = {"title": uniq("Мэдэгдэл-"), "body": "Агуулга", "audience_type": "all"}
    body.update(kw)
    r = api.post("/api/admin/notifications", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _inbox_ids(u, **qs):
    r = u.get("/api/notifications", query_string=qs)
    assert r.status_code == 200, r.get_json()
    return [x["id"] for x in r.get_json()["items"]]


@pytest.fixture
def plain_user(make_user):
    """Ямар ч эрхгүй дүртэй хэрэглэгч (inbox эрх шаардахгүйг батлах)."""
    return make_user([])


# ------------------------------- create -------------------------------
def test_send_all_immediately(api, plain_user):
    u, user = plain_user
    n = _notify(api, type="urgent")
    assert n["status"] == "sent" and n["sent_at"]
    assert n["type"] == "urgent"
    assert n["recipient_count"] >= 2           # admin + шинэ хэрэглэгч
    assert n["read_count"] == 0
    assert n["user_ids"] == []
    assert n["id"] in _inbox_ids(u)


def test_send_to_role(api, make_user):
    u1, user1 = make_user([])
    u2, _ = make_user([])
    n = _notify(api, audience_type="role", role_id=user1["role_id"])
    assert n["status"] == "sent"
    assert n["recipient_count"] == 1
    assert n["role_id"] == user1["role_id"] and n["role_name"]
    assert n["id"] in _inbox_ids(u1)
    assert n["id"] not in _inbox_ids(u2)


def test_send_picked(api, make_user):
    u1, user1 = make_user([])
    u2, _ = make_user([])
    n = _notify(api, audience_type="picked", user_ids=[user1["id"], user1["id"]])
    assert n["recipient_count"] == 1
    assert n["user_ids"] == [user1["id"]]
    assert n["id"] in _inbox_ids(u1)
    assert n["id"] not in _inbox_ids(u2)


def test_scheduled_future_not_sent(api, plain_user):
    u, user = plain_user
    n = _notify(api, audience_type="picked", user_ids=[user["id"]],
                scheduled_at="2099-01-01T09:00:00Z")
    assert n["status"] == "scheduled"
    assert n["scheduled_at"] == "2099-01-01 09:00:00"
    assert n["recipient_count"] == 0 and n["sent_at"] is None
    assert n["id"] not in _inbox_ids(u)
    api.delete(f"/api/admin/notifications/{n['id']}")


def test_scheduled_past_dispatched_lazily_on_admin_list(api, plain_user):
    u, user = plain_user
    n = _notify(api, audience_type="picked", user_ids=[user["id"]], scheduled_at=PAST)
    assert n["status"] == "scheduled"
    api.get("/api/admin/notifications")
    got = api.get(f"/api/admin/notifications/{n['id']}").get_json()
    assert got["status"] == "sent" and got["sent_at"]
    assert got["recipient_count"] == 1
    assert n["id"] in _inbox_ids(u)


def test_scheduled_past_dispatched_lazily_on_inbox(api, plain_user):
    u, user = plain_user
    n = _notify(api, audience_type="picked", user_ids=[user["id"]], scheduled_at=PAST)
    assert n["id"] in _inbox_ids(u)             # inbox уншихад л илгээгдэнэ
    assert api.get(f"/api/admin/notifications/{n['id']}").get_json()["status"] == "sent"


def test_draft_is_not_sent(api, plain_user):
    u, user = plain_user
    n = _notify(api, status="draft", audience_type="picked", user_ids=[user["id"]])
    assert n["status"] == "draft" and n["recipient_count"] == 0
    assert n["id"] not in _inbox_ids(u)


@pytest.mark.parametrize("override", [
    {"title": ""},
    {"title": None},
    {"body": "  "},
    {"title": "x" * 301},
    {"type": "spam"},
    {"audience_type": "everyone"},
    {"audience_type": None},
    {"audience_type": "role"},
    {"audience_type": "role", "role_id": 999999},
    {"audience_type": "role", "role_id": 1, "user_ids": [1]},
    {"audience_type": "picked"},
    {"audience_type": "picked", "user_ids": []},
    {"audience_type": "picked", "user_ids": "1"},
    {"audience_type": "picked", "user_ids": ["abc"]},
    {"audience_type": "picked", "user_ids": [999999]},
    {"audience_type": "picked", "user_ids": [1], "role_id": 1},
    {"audience_type": "all", "role_id": 1},
    {"audience_type": "all", "user_ids": [1]},
    {"scheduled_at": "tomorrow"},
    {"scheduled_at": 123},
    {"status": "archived"},
])
def test_create_validation(api, override):
    body = {"title": "t", "body": "b", "audience_type": "all"}
    body.update(override)
    r = api.post("/api/admin/notifications", json=body)
    assert r.status_code == 400, r.get_json()


def test_create_no_body(api):
    assert api.post("/api/admin/notifications").status_code == 400


# ------------------------------- read -------------------------------
def test_get_and_404(api):
    n = _notify(api, status="draft")
    r = api.get(f"/api/admin/notifications/{n['id']}")
    assert r.status_code == 200 and r.get_json()["title"] == n["title"]
    assert api.get("/api/admin/notifications/999999").status_code == 404
    api.delete(f"/api/admin/notifications/{n['id']}")


def test_list_shape_filters_paging(api):
    tag = uniq("ntf")
    d = _notify(api, title=f"{tag} a", status="draft")
    s = _notify(api, title=f"{tag} b", scheduled_at=FUTURE, type="reminder")
    r = api.get(f"/api/admin/notifications?search={tag}")
    body = r.get_json()
    assert set(body) == {"items", "total", "page", "per_page", "pages"}
    assert [x["id"] for x in body["items"]] == [s["id"], d["id"]]
    assert [x["id"] for x in api.get(
        f"/api/admin/notifications?search={tag}&status=draft").get_json()["items"]] == [d["id"]]
    assert [x["id"] for x in api.get(
        f"/api/admin/notifications?search={tag}&type=reminder").get_json()["items"]] == [s["id"]]
    p = api.get(f"/api/admin/notifications?search={tag}&per_page=1&page=2").get_json()
    assert p["pages"] == 2 and [x["id"] for x in p["items"]] == [d["id"]]
    assert api.get("/api/admin/notifications?per_page=999").get_json()["per_page"] == 100
    assert api.get("/api/admin/notifications?page=x").status_code == 400
    for n in (d, s):
        api.delete(f"/api/admin/notifications/{n['id']}")


# ------------------------------- delete -------------------------------
def test_delete_draft_and_scheduled(api):
    for kw in ({"status": "draft"}, {"scheduled_at": FUTURE}):
        n = _notify(api, **kw)
        r = api.delete(f"/api/admin/notifications/{n['id']}")
        assert r.status_code == 200 and r.get_json() == {"deleted": n["id"]}
        assert api.get(f"/api/admin/notifications/{n['id']}").status_code == 404
    assert api.delete("/api/admin/notifications/999999").status_code == 404


def test_delete_sent_is_422_unless_hard(api, plain_user):
    u, user = plain_user
    n = _notify(api, audience_type="picked", user_ids=[user["id"]])
    r = api.delete(f"/api/admin/notifications/{n['id']}")
    assert r.status_code == 422 and "error" in r.get_json()
    r = api.delete(f"/api/admin/notifications/{n['id']}?hard=1")
    assert r.status_code == 200
    assert api.get(f"/api/admin/notifications/{n['id']}").status_code == 404
    assert n["id"] not in _inbox_ids(u)         # recipients cascade


# ------------------------------- inbox -------------------------------
def test_inbox_needs_token_but_no_permission(anon, plain_user):
    u, _ = plain_user
    assert anon.get("/api/notifications").status_code == 401
    assert u.get("/api/notifications").status_code == 200
    assert u.get("/api/admin/notifications").status_code == 403
    assert u.post("/api/admin/notifications",
                  json={"title": "t", "body": "b", "audience_type": "all"}).status_code == 403


def test_inbox_unread_and_mark_read(api, plain_user):
    u, user = plain_user
    n1 = _notify(api, audience_type="picked", user_ids=[user["id"]])
    n2 = _notify(api, audience_type="picked", user_ids=[user["id"]])
    body = u.get("/api/notifications").get_json()
    assert body["unread_count"] == 2
    assert [x["id"] for x in body["items"]] == [n2["id"], n1["id"]]
    assert body["items"][0]["read_at"] is None

    r = u.post(f"/api/notifications/{n1['id']}/read")
    assert r.status_code == 200 and r.get_json() == {"status": True}
    first = [x for x in u.get("/api/notifications").get_json()["items"]
             if x["id"] == n1["id"]][0]["read_at"]
    assert first
    u.post(f"/api/notifications/{n1['id']}/read")      # дахин уншихад огноо хэвээр
    again = [x for x in u.get("/api/notifications").get_json()["items"]
             if x["id"] == n1["id"]][0]["read_at"]
    assert again == first

    body = u.get("/api/notifications?unread=1").get_json()
    assert body["unread_count"] == 1
    assert [x["id"] for x in body["items"]] == [n2["id"]]
    assert api.get(f"/api/admin/notifications/{n1['id']}").get_json()["read_count"] == 1


def test_inbox_limit(api, plain_user):
    u, user = plain_user
    for _ in range(3):
        _notify(api, audience_type="picked", user_ids=[user["id"]])
    assert len(_inbox_ids(u, limit=2)) == 2
    assert u.get("/api/notifications?limit=x").status_code == 400


def test_mark_read_foreign_or_missing(api, make_user):
    u1, user1 = make_user([])
    u2, _ = make_user([])
    n = _notify(api, audience_type="picked", user_ids=[user1["id"]])
    assert u2.post(f"/api/notifications/{n['id']}/read").status_code == 404
    assert u1.post("/api/notifications/999999/read").status_code == 404


def test_all_audience_skips_inactive(api, make_user):
    u, user = make_user([])
    r = api.put(f"/api/user/{user['id']}", json={"is_active": 0})
    assert r.status_code == 200, r.get_json()
    n = _notify(api)
    conn_check = api.get(f"/api/admin/notifications/{n['id']}").get_json()
    # идэвхгүй хэрэглэгчийн токен хүчинтэй хэвээр ч inbox-д нь ирэхгүй
    inbox = u.get("/api/notifications")
    if inbox.status_code == 200:
        assert n["id"] not in [x["id"] for x in inbox.get_json()["items"]]
    assert conn_check["status"] == "sent"
