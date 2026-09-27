"""Хууль тогтоомж — admin/legal.py (/api/legal_document...) + client/legal.py (/api/portal/...)."""
import io
import os

import pytest

import admin.content as content
import client.search as search_mod
from conftest import uniq, PDF_BYTES

LINK = {"display_mode": "link", "external_url": "https://legalinfo.mn/mn/detail?lawId=1"}


def _doc(api, **kw):
    body = {"title": uniq("Хөдөлмөрийн тухай хууль "), **LINK}
    body.update(kw)
    r = api.post("/api/legal_document", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _upload_pdf(api):
    r = api.post("/api/upload", data={"file": (io.BytesIO(PDF_BYTES), "doc.pdf")},
                 content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["url"]


# ============================== document ==============================
def test_modes_crud_and_admin_shape(api):
    link = _doc(api, category="Хууль", published_date="2021.07.02", source_name="legalinfo.mn")
    assert link["published_date"] == "2021-07-02" and link["is_visible"] is True
    assert link["sort_order"] == 0 and link["created_at"] and link["updated_at"]
    pdf = _upload_pdf(api)
    f = _doc(api, display_mode="file", pdf_url=pdf, external_url=None)
    d = _doc(api, display_mode="detail", external_url=None)
    got = api.get(f"/api/legal_document/{d['id']}").get_json()
    assert got["display_mode"] == "detail" and got["blocks"] == []
    r = api.put(f"/api/legal_document/{link['id']}", json={"title": "Шинэ нэр"})
    assert r.status_code == 200 and r.get_json()["title"] == "Шинэ нэр"
    assert api.patch(f"/api/legal_document/{link['id']}", json={"is_visible": False}) \
        .get_json()["is_visible"] is False
    for x in (link, f, d):
        assert api.delete(f"/api/legal_document/{x['id']}").get_json() == {"deleted": x["id"]}
    assert api.get(f"/api/legal_document/{link['id']}").status_code == 404


@pytest.mark.parametrize("body", [
    {"display_mode": "link", "external_url": "https://a.mn"},            # title заавал
    {"title": "A", "display_mode": "pdf"},                                # буруу горим
    {"title": "A"},                                                        # горим заавал
    {"title": "A", "display_mode": "link"},                                # external_url заавал
    {"title": "A", "display_mode": "link", "external_url": "/local"},      # http(s) биш
    {"title": "A", "display_mode": "link", "external_url": "javascript:alert(1)"},
    {"title": "A", "display_mode": "file"},                                # pdf_url заавал
    {"title": "A", "display_mode": "detail", "pdf_url": "//evil.com/x.pdf"},
    {"title": "A", "display_mode": "detail", "published_date": "2021-13-40"},
    {"title": "A", "display_mode": "detail", "sort_order": "x"},
    {"title": "A", "display_mode": "detail", "is_visible": "maybe"},
    {"title": "x" * 501, "display_mode": "detail"},
])
def test_document_validation(api, body):
    r = api.post("/api/legal_document", json=body)
    assert r.status_code == 400 and "error" in r.get_json()


def test_partial_update_checks_merged_mode(api):
    d = _doc(api, display_mode="detail", external_url=None)
    assert api.patch(f"/api/legal_document/{d['id']}", json={"display_mode": "link"}).status_code == 400
    r = api.patch(f"/api/legal_document/{d['id']}",
                  json={"display_mode": "link", "external_url": "https://x.mn"})
    assert r.status_code == 200
    assert api.patch(f"/api/legal_document/{d['id']}", json={}).status_code == 400
    api.delete(f"/api/legal_document/{d['id']}")


def test_ordering_sort_then_newest_date(api):
    tag = uniq("Эрэмбэ")
    a = _doc(api, title=f"{tag} a", sort_order=5, published_date="2020-01-01")
    b = _doc(api, title=f"{tag} b", sort_order=5, published_date="2023-01-01")
    c = _doc(api, title=f"{tag} c", sort_order=5)                          # огноогүй -> сүүлд
    first = _doc(api, title=f"{tag} d", sort_order=-100)
    ids = [x["id"] for x in api.get("/api/legal_document").get_json() if x["title"].startswith(tag)]
    assert ids == [first["id"], b["id"], a["id"], c["id"]]
    paged = api.get("/api/legal_document?per_page=2").get_json()
    assert set(paged) == {"items", "total", "page", "per_page", "pages"}
    for x in (a, b, c, first):
        api.delete(f"/api/legal_document/{x['id']}")


# =============================== blocks ===============================
def test_blocks_crud_reorder(api):
    d = _doc(api, display_mode="detail", external_url=None)
    base = f"/api/legal_document/{d['id']}/blocks"
    t = api.post(base, json={"type": "text", "text": "<p>Товч</p>"}).get_json()
    f = api.post(base, json={"type": "file", "url": "https://x.mn/a.pdf", "name": "a.pdf",
                             "mime_type": "application/pdf", "size": 10}).get_json()
    ln = api.post(base, json={"type": "link", "url": "https://legalinfo.mn", "title": "Эх"}).get_json()
    assert [t["sort_order"], f["sort_order"], ln["sort_order"]] == [1, 2, 3]
    assert set(t) == {"id", "legal_document_id", "type", "sort_order", "text"}
    assert set(f) >= {"url", "name", "mime_type", "size"} and "text" not in f
    assert set(ln) == {"id", "legal_document_id", "type", "sort_order", "url", "title"}
    assert api.post(base, json={"type": "image", "url": "https://x"}).status_code == 400
    assert api.post(base, json={"type": "file"}).status_code == 400          # url заавал
    assert api.post(base, json={"type": "link", "url": "javascript:x"}).status_code == 400

    r = api.post(f"{base}/reorder", json={"blocks": [{"id": ln["id"], "sort_order": 1},
                                                     {"id": t["id"], "sort_order": 2},
                                                     {"id": f["id"], "sort_order": 3}]})
    assert r.status_code == 200 and [b["id"] for b in r.get_json()] == [ln["id"], t["id"], f["id"]]
    assert [b["id"] for b in api.get(base).get_json()] == [ln["id"], t["id"], f["id"]]
    assert api.post(f"{base}/reorder", json={"blocks": [{"id": 999999}]}).status_code == 404
    assert api.post(f"{base}/reorder", json={}).status_code == 400

    r = api.put(f"/api/legal_document_block/{ln['id']}", json={"title": "Шинэ"})
    assert r.status_code == 200 and r.get_json()["title"] == "Шинэ" and r.get_json()["type"] == "link"
    assert api.patch(f"/api/legal_document_block/{t['id']}", json={"text": "B"}).get_json()["text"] == "B"
    assert api.get(f"/api/legal_document_block/{t['id']}").get_json()["text"] == "B"
    assert api.delete(f"/api/legal_document_block/{t['id']}").get_json() == {"deleted": t["id"]}
    assert api.get(f"/api/legal_document_block/{t['id']}").status_code == 404
    api.delete(f"/api/legal_document/{d['id']}")
    assert api.get(f"/api/legal_document_block/{f['id']}").status_code == 404   # cascade
    assert api.get("/api/legal_document/999999/blocks").status_code == 404


def test_replaced_file_removed_deleted_kept(api):
    main, attached, swapped = _upload_pdf(api), _upload_pdf(api), _upload_pdf(api)
    path = lambda u: os.path.join(content.UPLOAD_DIR, os.path.basename(u))  # noqa: E731
    d = _doc(api, display_mode="detail", external_url=None, pdf_url=main)
    b = api.post(f"/api/legal_document/{d['id']}/blocks",
                 json={"type": "file", "url": attached, "name": "x.pdf"}).get_json()
    api.patch(f"/api/legal_document/{d['id']}", json={"pdf_url": swapped})
    assert not os.path.exists(path(main))                       # солигдсон PDF арилсан
    api.delete(f"/api/legal_document/{d['id']}")
    assert os.path.exists(path(swapped)) and os.path.exists(path(attached))   # soft delete
    assert b["url"] == attached


# =============================== portal ===============================
def test_portal_list_and_detail(api, anon):
    visible = _doc(api, category="Журам", source_name="Холбоо", display_mode="detail",
                   external_url=None, published_date="2022-02-02")
    hidden = _doc(api, is_visible=False)
    api.post(f"/api/legal_document/{visible['id']}/blocks", json={"type": "text", "text": "T"})
    r = anon.get("/api/portal/legal_documents")
    assert r.status_code == 200
    items = r.get_json()["items"]
    mine = next(x for x in items if x["id"] == visible["id"])
    assert set(mine) == {"id", "title", "category", "published_date", "source_name",
                         "display_mode", "external_url", "pdf_url"}
    assert hidden["id"] not in [x["id"] for x in items]
    det = anon.get(f"/api/portal/legal_documents/{visible['id']}").get_json()
    assert det["title"] == visible["title"] and [b["text"] for b in det["blocks"]] == ["T"]
    r = anon.get(f"/api/portal/legal_documents/{hidden['id']}")
    assert r.status_code == 404 and "error" in r.get_json()
    assert anon.get("/api/portal/legal_documents/999999").status_code == 404
    for x in (visible, hidden):
        api.delete(f"/api/legal_document/{x['id']}")


# ================================ auth ================================
def test_permissions_blocks_use_legal_document(anon, make_user, api):
    assert anon.get("/api/legal_document").status_code == 401
    d = _doc(api, display_mode="detail", external_url=None)
    blk = api.post(f"/api/legal_document/{d['id']}/blocks", json={"type": "text", "text": "x"}).get_json()
    reader, _ = make_user(["legal_document.read"])
    assert reader.get("/api/legal_document").status_code == 200
    assert reader.get(f"/api/legal_document/{d['id']}/blocks").status_code == 200
    assert reader.post("/api/legal_document", json={}).status_code == 403
    assert reader.post(f"/api/legal_document/{d['id']}/blocks", json={}).status_code == 403
    assert reader.patch(f"/api/legal_document_block/{blk['id']}", json={}).status_code == 403
    editor, _ = make_user(["legal_document.create", "legal_document.update"])   # news_block-гүй
    assert editor.post(f"/api/legal_document/{d['id']}/blocks",
                       json={"type": "text", "text": "y"}).status_code == 201
    assert editor.post(f"/api/legal_document/{d['id']}/blocks/reorder",
                       json={"blocks": [{"id": blk["id"]}]}).status_code == 200
    news_only, _ = make_user(["news_block.create", "news_block.read"])
    assert news_only.get(f"/api/legal_document/{d['id']}/blocks").status_code == 403
    codes = {p["code"] for p in api.get("/api/role/1").get_json()["permissions"]}
    assert {f"legal_document.{a}" for a in ("create", "read", "update", "delete")} <= codes
    api.delete(f"/api/legal_document/{d['id']}")


def test_menu_type_legal(api):
    r = api.post("/api/menu", json={"title": uniq("Хууль тогтоомж"), "type": "legal"})
    assert r.status_code == 201 and r.get_json()["type"] == "legal"
    api.delete(f"/api/menu/{r.get_json()['id']}")


def test_search_finds_legal_documents(api, anon):
    search_mod.reset_state()
    k = uniq("Хуульхайлт")
    link = _doc(api, title=f"{k} гадаад")
    det = _doc(api, title=f"{k} дэлгэрэнгүй", display_mode="detail", external_url=None)
    items = anon.get("/api/portal/search/suggest", query_string={"q": k}).get_json()["items"]
    paths = {i["id"]: i["path"] for i in items if i["type"] == "document"}
    assert paths[link["id"]] == LINK["external_url"] and paths[det["id"]] == f"/legal/{det['id']}"
    for x in (link, det):
        api.delete(f"/api/legal_document/{x['id']}")
    search_mod.reset_state()
