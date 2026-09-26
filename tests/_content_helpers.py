"""admin/content.py — порталын цэс, контент хуудас, блок, файл байршуулалт — хуваалцсан туслахууд (test_content_*.py ашиглана)."""

import io
import os

from conftest import uniq, PNG_BYTES
import admin.content as content


# ----------------------------- туслахууд -----------------------------
def _menu(api, **body):
    body.setdefault("title", uniq("Цэс "))
    r = api.post("/api/menu", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _page_menu(api):
    """type='page' цэс + түүний автоматаар үүссэн хуудас."""
    m = _menu(api, type="page")
    assert m["page_id"]
    return m, m["page_id"]


def _upload(api, name="a.png", data=PNG_BYTES):
    return api.post("/api/upload", data={"file": (io.BytesIO(data), name)},
                    content_type="multipart/form-data")


def _disk_path(url):
    return os.path.join(content.UPLOAD_DIR, os.path.basename(url))
