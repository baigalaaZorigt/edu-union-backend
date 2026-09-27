"""admin/settings.py — порталын тохиргоо (singleton).

Мөр нь бүх session-д хуваалцагдана: тест бүр эх утгыг хадгалж, төгсгөлд нь
PUT-ээр яг буцааж тавина.
"""
import io
import os

import pytest

from conftest import PNG_BYTES
import admin.content as content
from core.settings_core import SETTINGS_FIELDS


@pytest.fixture
def original(api):
    """Эх утгыг хадгалаад тестийн дараа сэргээнэ."""
    orig = api.get("/api/portal_settings").get_json()
    try:
        yield orig
    finally:
        body = {f: orig[f] for f in SETTINGS_FIELDS}
        r = api.put("/api/portal_settings", json=body)
        assert r.status_code == 200, r.get_json()
        restored = api.get("/api/portal_settings").get_json()
        assert {f: restored[f] for f in SETTINGS_FIELDS} == body


def _full(orig, **over):
    body = {f: orig[f] for f in SETTINGS_FIELDS}
    body.update(over)
    return body


def test_get_settings_shape(api, original):
    assert set(SETTINGS_FIELDS) <= set(original)
    assert "updated_at" in original
    assert isinstance(original["phones"], list) and original["phones"]


def test_settings_require_token_and_permission(anon, make_user):
    assert anon.get("/api/portal_settings").status_code == 401
    assert anon.patch("/api/portal_settings", json={"hero_title": "x"}).status_code == 401
    u, _ = make_user(["member.read"])
    assert u.get("/api/portal_settings").status_code == 403
    assert u.put("/api/portal_settings", json={"hero_title": "x"}).status_code == 403


def test_settings_readonly_permission(make_user):
    u, _ = make_user(["portal_settings.read"])
    assert u.get("/api/portal_settings").status_code == 200
    assert u.patch("/api/portal_settings", json={"hero_title": "x"}).status_code == 403


def test_public_settings_without_token(anon, api, original):
    for url in ("/api/public/portal_settings", "/api/portal/portal_settings"):
        r = anon.get(url)
        assert r.status_code == 200
        assert r.get_json() == api.get("/api/portal_settings").get_json()


def test_patch_merges(api, original):
    r = api.patch("/api/portal_settings", json={"hero_title": "  Шинэ гарчиг  "})
    assert r.status_code == 200
    body = r.get_json()
    assert body["hero_title"] == "Шинэ гарчиг"                      # trim хийгдэнэ
    assert body["header_title"] == original["header_title"]
    assert body["phones"] == original["phones"]
    assert api.get("/api/public/portal_settings").get_json()["hero_title"] == "Шинэ гарчиг"


def test_put_overwrites_whole_row(api, original):
    r = api.put("/api/portal_settings", json={"phones": ["99119911"], "header_title": "H"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["phones"] == ["99119911"] and body["header_title"] == "H"
    assert body["hero_title"] is None and body["address"] is None     # өгөөгүй -> NULL


def test_put_requires_phones(api, original):
    assert api.put("/api/portal_settings", json={"header_title": "H"}).status_code == 400
    assert api.get("/api/portal_settings").get_json()["header_title"] == original["header_title"]


def test_phones_validation(api, original):
    r = api.patch("/api/portal_settings", json={"phones": [" 111 ", "", 222]})
    assert r.status_code == 200 and r.get_json()["phones"] == ["111", "222"]
    assert api.patch("/api/portal_settings", json={"phones": "111"}).status_code == 400
    assert api.patch("/api/portal_settings", json={"phones": []}).status_code == 400
    assert api.patch("/api/portal_settings", json={"phones": ["  "]}).status_code == 400


@pytest.mark.parametrize("field,value", [
    ("facebook_url", "facebook.com/x"),
    ("youtube_url", "ftp://youtube.com/x"),
    ("map_embed_url", "https://evil.example/embed"),
    ("map_embed_url", "google.com/maps/embed?pb=1"),
    ("header_title", 123),
    ("hero_text", "x" * 2001),
])
def test_field_validation(api, original, field, value):
    assert api.patch("/api/portal_settings", json={field: value}).status_code == 400


def test_valid_urls_and_clearing(api, original):
    r = api.patch("/api/portal_settings", json={
        "facebook_url": "https://facebook.com/x",
        "youtube_url": "http://youtube.com/@x",
        "map_embed_url": "https://www.google.com/maps/embed?pb=abc",
        "website": "fmesu.mn",                       # website-д схем шаардахгүй
    })
    assert r.status_code == 200
    assert r.get_json()["map_embed_url"] == "https://www.google.com/maps/embed?pb=abc"
    r = api.patch("/api/portal_settings", json={"youtube_url": "", "facebook_url": None})
    assert r.status_code == 200
    assert r.get_json()["youtube_url"] is None and r.get_json()["facebook_url"] is None


def test_empty_body_rejected(api, original):
    assert api.patch("/api/portal_settings", json={}).status_code == 400
    assert api.patch("/api/portal_settings", json={"unknown": 1}).status_code == 400
    assert api.put("/api/portal_settings", data="nope",
                   content_type="application/json").status_code == 400


def test_logo_replacement_removes_old_upload(api, original):
    def up():
        return api.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "l.png")},
                        content_type="multipart/form-data").get_json()["url"]

    def path(u):
        return os.path.join(content.UPLOAD_DIR, os.path.basename(u))
    old, new = up(), up()
    assert api.patch("/api/portal_settings", json={"logo_url": old}).status_code == 200
    assert api.patch("/api/portal_settings", json={"logo_url": new}).status_code == 200
    assert not os.path.exists(path(old))
    assert os.path.isfile(path(new))
    # сэргээхэд (original fixture) шинэ лого ч дискнээс арилна
    content.remove_upload(new)


def test_get_autocreates_row_when_missing(api, original):
    from sqlalchemy import delete, select
    from core import db
    from core.orm import new_session
    from core.orm.models import PortalSettings
    s = new_session()
    saved = s.scalars(select(PortalSettings)).one().to_dict()
    s.execute(delete(PortalSettings))
    s.commit()
    s.close()
    try:
        r = api.get("/api/portal_settings")
        assert r.status_code == 200
        assert r.get_json()["header_title"] == db.DEFAULT_PORTAL_SETTINGS["header_title"]
        assert r.get_json()["phones"] == db.DEFAULT_PORTAL_SETTINGS["phones"]
    finally:
        s = new_session()
        s.execute(delete(PortalSettings))
        s.add(PortalSettings(**saved))
        s.commit()
        s.close()
