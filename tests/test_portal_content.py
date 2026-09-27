"""Токенгүй портал контент — client/content.py. Хариу admin-ийнхтэй ЯГ ижил, харагдах нь л."""
import io

import pytest

import client.content as portal
from conftest import uniq, PNG_BYTES


def _menu(api, **body):
    body.setdefault("title", uniq("Портал цэс "))
    body.setdefault("type", "page")
    r = api.post("/api/menu", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _publish(api, menu, status="published"):
    r = api.put(f"/api/page/{menu['page_id']}", json={"status": status, "body": "<p>Агуулга</p>"})
    assert r.status_code == 200, r.get_json()


def _block(api, page_id, **body):
    r = api.post("/api/page_block", json={"page_id": page_id, **body})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


@pytest.fixture
def site(api):
    """харагдах эцэг + хүүхэд (нийтлэгдсэн), нууцалсан цэс, нууцалсан эцгийн хүүхэд, ноорог."""
    parent = _menu(api)
    child = _menu(api, parent_id=parent["id"])
    hidden = _menu(api, is_visible=False)
    orphan = _menu(api, parent_id=hidden["id"])
    draft = _menu(api)
    for m in (parent, child, hidden, orphan):
        _publish(api, m)
    _publish(api, draft, "draft")
    for m in (parent, child, hidden, orphan, draft):
        _block(api, m["page_id"], type="text", text=f"<p>{m['title']}</p>")
    _block(api, child["page_id"], type="link", url="https://legalinfo.mn", title="Холбоос")
    yield {"parent": parent, "child": child, "hidden": hidden, "orphan": orphan, "draft": draft}
    for m in (parent, hidden, draft):
        api.delete(f"/api/menu/{m['id']}")


# ================================ menu ================================
def test_menu_same_shape_only_visible(api, anon, site):
    admin_items = {m["id"]: m for m in api.get("/api/menu").get_json()}
    r = anon.get("/api/portal/menu")
    assert r.status_code == 200
    portal_items = {m["id"]: m for m in r.get_json()}
    for key in ("parent", "child", "draft"):                       # draft цэс өөрөө харагдана
        mid = site[key]["id"]
        assert portal_items[mid] == admin_items[mid]                # ЯГ ижил dict
    for key in ("hidden", "orphan"):                               # нууцалсан / эцэг нь нууц
        assert site[key]["id"] not in portal_items
    assert all(m["is_visible"] for m in portal_items.values())


def test_menu_tree_filters_and_paging(api, anon, site):
    tree = anon.get("/api/portal/menu?tree=1").get_json()
    node = next(n for n in tree if n["id"] == site["parent"]["id"])
    assert [c["id"] for c in node["children"]] == [site["child"]["id"]]
    assert site["hidden"]["id"] not in [n["id"] for n in tree]
    kids = anon.get(f"/api/portal/menu?parent_id={site['parent']['id']}").get_json()
    assert [k["id"] for k in kids] == [site["child"]["id"]]
    assert anon.get(f"/api/portal/menu?parent_id={site['hidden']['id']}").get_json() == []
    assert anon.get("/api/portal/menu?is_visible=0").get_json() == anon.get("/api/portal/menu").get_json()
    d = anon.get("/api/portal/menu?per_page=2").get_json()
    assert set(d) == {"items", "total", "page", "per_page", "pages"} and len(d["items"]) <= 2


# ================================ page ================================
def test_page_same_as_admin_only_public(api, anon, site):
    for key in ("parent", "child"):
        mid = site[key]["id"]
        r = anon.get(f"/api/portal/page/{mid}")
        assert r.status_code == 200
        assert r.get_json() == api.get(f"/api/page/{mid}").get_json()   # ЯГ ижил
    child = anon.get(f"/api/portal/page/{site['child']['id']}").get_json()
    assert [b["type"] for b in child["blocks"]] == ["text", "link"]
    assert set(child) >= {"blocks", "images", "files", "videos"}
    for key in ("hidden", "orphan", "draft"):
        r = anon.get(f"/api/portal/page/{site[key]['id']}")
        assert r.status_code == 404 and r.get_json()["error"] == "Энэ цэсэнд контент хуудас алга"
    assert anon.get("/api/portal/page/999999").status_code == 404


# ============================== page_block ==============================
def test_page_block_same_as_admin_only_public(api, anon, site):
    pid = site["child"]["page_id"]
    r = anon.get(f"/api/portal/page_block?page_id={pid}")
    assert r.status_code == 200
    assert r.get_json() == api.get(f"/api/page_block?page_id={pid}").get_json()
    assert anon.get(f"/api/portal/page_block?page_id={pid}&type=link").get_json() == \
        api.get(f"/api/page_block?page_id={pid}&type=link").get_json()
    for key in ("hidden", "orphan", "draft"):
        assert anon.get(f"/api/portal/page_block?page_id={site[key]['page_id']}").get_json() == []
    all_public = {b["page_id"] for b in anon.get("/api/portal/page_block").get_json()}
    assert site["draft"]["page_id"] not in all_public and site["hidden"]["page_id"] not in all_public
    assert anon.get("/api/portal/page_block?page_id=abc").get_json() == []
    d = anon.get(f"/api/portal/page_block?page_id={pid}&per_page=1").get_json()
    assert d["total"] == 2 and len(d["items"]) == 1


# ================================ upload ================================
def _upload(client, name="a.png", data=PNG_BYTES, ip="203.0.113.50"):
    return client.post("/api/portal/upload", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data", headers={"X-Real-IP": ip})


def test_upload_token_free_same_shape(anon, api):
    portal._uploads.clear()
    r = _upload(anon)
    assert r.status_code == 201
    d = r.get_json()
    assert set(d) == {"url", "name", "mime_type", "size"} and d["mime_type"] == "image/png"
    assert d["url"].startswith("/uploads/content/")
    admin = api.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "a.png")},
                     content_type="multipart/form-data").get_json()
    assert set(admin) == set(d) and admin["size"] == d["size"]
    assert anon.get(d["url"]).data == PNG_BYTES                        # буцааж уншигдана
    assert _upload(anon, name="x.exe", data=b"MZ").status_code == 400
    assert anon.post("/api/portal/upload", data={}, content_type="multipart/form-data").status_code == 400


def test_upload_rate_limit(anon, monkeypatch):
    portal._uploads.clear()
    monkeypatch.setattr(portal, "UPLOAD_LIMIT", 2)
    assert [_upload(anon, ip="198.51.100.9").status_code for _ in range(3)] == [201, 201, 429]
    r = _upload(anon, ip="198.51.100.9")
    assert r.status_code == 429 and "error" in r.get_json()
    assert _upload(anon, ip="198.51.100.10").status_code == 201        # өөр IP
    portal._uploads.clear()
