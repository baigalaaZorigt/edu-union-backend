"""Порталын нүүр хуудас — admin/home.py (/api/banner|partner) + client/home.py (/api/portal/...)."""
import io
import os
from datetime import datetime, timedelta, timezone

import pytest

import admin.content as content
from conftest import uniq, PNG_BYTES


def _utc(delta_hours):
    return (datetime.now(timezone.utc) + timedelta(hours=delta_hours)).strftime("%Y-%m-%d %H:%M:%S")


def _upload_png(api):
    r = api.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "b.png")},
                 content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["url"]


def _public_ids(anon, kind):
    r = anon.get(f"/api/portal/{kind}")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "public, max-age=300"
    return [x["id"] for x in r.get_json()["items"]]


# ================================ banner ================================
def test_banner_crud_and_public(api, anon):
    img = _upload_png(api)
    title = uniq("Баннер")
    r = api.post("/api/banner", json={"title": title, "image_url": img,
                                      "link_url": "/news/1", "sort_order": 5})
    assert r.status_code == 201, r.get_json()
    b = r.get_json()
    assert b["is_visible"] is True and b["sort_order"] == 5 and b["starts_at"] is None
    bid = b["id"]
    assert api.get(f"/api/banner/{bid}").get_json()["title"] == title
    assert bid in [x["id"] for x in api.get("/api/banner").get_json()]

    # портал: токенгүй, зөвхөн 4 талбар
    items = anon.get("/api/portal/banners").get_json()["items"]
    mine = next(x for x in items if x["id"] == bid)
    assert mine == {"id": bid, "title": title, "image_url": img, "link_url": "/news/1"}

    # нуух -> порталд алга, админд байна; PUT ба PATCH хоёулаа
    assert api.put(f"/api/banner/{bid}", json={"is_visible": False}).status_code == 200
    assert bid not in _public_ids(anon, "banners")
    assert bid in [x["id"] for x in api.get("/api/banner").get_json()]
    r = api.patch(f"/api/banner/{bid}", json={"is_visible": True, "title": ""})
    assert r.status_code == 200 and r.get_json()["title"] is None
    assert bid in _public_ids(anon, "banners")

    # зураг солиход хуучин файл дискнээс арилна; устгахад шинэ нь ч арилна
    old_path = os.path.join(content.UPLOAD_DIR, os.path.basename(img))
    new = _upload_png(api)
    assert api.patch(f"/api/banner/{bid}", json={"image_url": new}).status_code == 200
    assert not os.path.exists(old_path)
    new_path = os.path.join(content.UPLOAD_DIR, os.path.basename(new))
    assert os.path.exists(new_path)
    assert api.delete(f"/api/banner/{bid}").get_json() == {"deleted": bid}
    assert not os.path.exists(new_path)
    assert api.get(f"/api/banner/{bid}").status_code == 404
    assert api.delete(f"/api/banner/{bid}").status_code == 404
    assert api.patch(f"/api/banner/{bid}", json={"title": "x"}).status_code == 404


def test_banner_ordering(api):
    a = api.post("/api/banner", json={"image_url": "https://x.mn/a.png", "sort_order": 2}).get_json()
    b = api.post("/api/banner", json={"image_url": "https://x.mn/b.png", "sort_order": 1}).get_json()
    ids = [x["id"] for x in api.get("/api/banner").get_json()]
    assert ids.index(b["id"]) < ids.index(a["id"])
    api.delete(f"/api/banner/{a['id']}")
    api.delete(f"/api/banner/{b['id']}")


def test_banner_schedule_window(api, anon):
    def mk(**kw):
        r = api.post("/api/banner", json={"image_url": "https://x.mn/s.png", **kw})
        assert r.status_code == 201, r.get_json()
        return r.get_json()["id"]
    live = mk(starts_at=_utc(-1), ends_at=_utc(1))
    future = mk(starts_at=_utc(2))
    expired = mk(ends_at=_utc(-2))
    open_end = mk(starts_at=_utc(-5))
    ids = _public_ids(anon, "banners")
    assert live in ids and open_end in ids
    assert future not in ids and expired not in ids
    # админ бүгдийг харна
    admin_ids = [x["id"] for x in api.get("/api/banner").get_json()]
    assert {live, future, expired, open_end} <= set(admin_ids)
    for i in (live, future, expired, open_end):
        api.delete(f"/api/banner/{i}")


def test_banner_datetime_normalized_to_utc(api):
    r = api.post("/api/banner", json={"image_url": "https://x.mn/t.png",
                                      "starts_at": "2026-10-01T09:00:00+08:00",
                                      "ends_at": "2026-10-02T00:00:00Z"})
    assert r.status_code == 201, r.get_json()
    b = r.get_json()
    assert b["starts_at"] == "2026-10-01 01:00:00"
    assert b["ends_at"] == "2026-10-02 00:00:00"
    r = api.patch(f"/api/banner/{b['id']}", json={"starts_at": "2026-10-05"})
    assert r.status_code == 400                     # нийлмэл төлөвөөр ends < starts
    r = api.patch(f"/api/banner/{b['id']}", json={"ends_at": None, "starts_at": "2026-10-05"})
    assert r.status_code == 200 and r.get_json()["starts_at"] == "2026-10-05 00:00:00"
    api.delete(f"/api/banner/{b['id']}")


@pytest.mark.parametrize("body", [
    {},                                                    # image_url заавал
    {"image_url": ""},
    {"image_url": "javascript:alert(1)"},
    {"image_url": "//evil.com/x.png"},
    {"image_url": "/a.png", "link_url": "javascript:alert(1)"},
    {"image_url": "/a.png", "sort_order": "abc"},
    {"image_url": "/a.png", "sort_order": True},
    {"image_url": "/a.png", "is_visible": "maybe"},
    {"image_url": "/a.png", "starts_at": "not a date"},
    {"image_url": "/a.png", "starts_at": 123},
    {"image_url": "/a.png", "starts_at": "2026-10-05", "ends_at": "2026-10-01"},
    {"image_url": "/a.png", "title": 5},
    {"image_url": "/a.png", "title": "x" * 501},
])
def test_banner_validation(api, body):
    r = api.post("/api/banner", json=body)
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_banner_update_errors(api):
    bid = api.post("/api/banner", json={"image_url": "/a.png"}).get_json()["id"]
    assert api.put(f"/api/banner/{bid}", json={"image_url": ""}).status_code == 400
    assert api.put(f"/api/banner/{bid}", json={"unknown": 1}).status_code == 400
    assert api.put(f"/api/banner/{bid}").status_code == 400
    api.delete(f"/api/banner/{bid}")


# ================================ partner ================================
def test_partner_crud_and_public(api, anon):
    name = uniq("Боловсролын яам")
    r = api.post("/api/partner", json={"name": name, "url": "https://moe.gov.mn",
                                       "icon": "🏛️", "sort_order": 3})
    assert r.status_code == 201, r.get_json()
    p = r.get_json()
    pid = p["id"]
    assert p["is_visible"] is True and p["icon"] == "🏛️"
    assert api.get(f"/api/partner/{pid}").get_json()["name"] == name

    items = anon.get("/api/portal/partners").get_json()["items"]
    assert next(x for x in items if x["id"] == pid) == \
        {"id": pid, "name": name, "url": "https://moe.gov.mn", "icon": "🏛️"}

    assert api.put(f"/api/partner/{pid}", json={"is_visible": 0}).status_code == 200
    assert pid not in _public_ids(anon, "partners")
    assert pid in [x["id"] for x in api.get("/api/partner").get_json()]
    r = api.patch(f"/api/partner/{pid}", json={"is_visible": "true", "url": "http://moe.mn"})
    assert r.status_code == 200 and r.get_json()["url"] == "http://moe.mn"
    assert pid in _public_ids(anon, "partners")

    assert api.delete(f"/api/partner/{pid}").get_json() == {"deleted": pid}
    assert api.get(f"/api/partner/{pid}").status_code == 404


@pytest.mark.parametrize("body", [
    {"url": "https://a.mn"},                               # name заавал
    {"name": "A"},                                         # url заавал
    {"name": "A", "url": "moe.gov.mn"},                    # схемгүй
    {"name": "A", "url": "/relative"},
    {"name": "A", "url": "ftp://a.mn"},
    {"name": " ", "url": "https://a.mn"},
    {"name": "A", "url": "https://a.mn", "icon": "x" * 17},
    {"name": "A", "url": "https://a.mn", "sort_order": "z"},
])
def test_partner_validation(api, body):
    r = api.post("/api/partner", json=body)
    assert r.status_code == 400 and "error" in r.get_json()


# ================================ эрх ================================
def test_home_auth(anon, make_user):
    assert anon.get("/api/banner").status_code == 401
    assert anon.post("/api/partner", json={}).status_code == 401
    reader, _ = make_user(["banner.read", "partner.read"])
    assert reader.get("/api/banner").status_code == 200
    assert reader.get("/api/partner").status_code == 200
    assert reader.post("/api/banner", json={"image_url": "/a.png"}).status_code == 403
    assert reader.delete("/api/partner/1").status_code == 403


def test_admin_role_has_home_permissions(api):
    codes = {p["code"] for p in api.get("/api/role/1").get_json()["permissions"]}
    assert {f"{r}.{a}" for r in ("banner", "partner")
            for a in ("create", "read", "update", "delete")} <= codes
