"""Мэдээ, зар — /api/admin/news..., /api/admin/news_blocks/..., /api/portal/news — хуваалцсан туслахууд (test_news_*.py ашиглана)."""

import io

from conftest import uniq, PNG_BYTES


def _news(api, **kw):
    body = {"title": uniq("Мэдээ-"), "category": "Мэдээ", "summary": "товч"}
    body.update(kw)
    r = api.post("/api/admin/news", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _upload_png(api):
    r = api.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "a.png")},
                 content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["url"]
