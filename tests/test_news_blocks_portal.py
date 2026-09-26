"""Мэдээ, зар — /api/admin/news..., /api/admin/news_blocks/..., /api/portal/news — blocks, portal."""

import pytest

from conftest import uniq

from _news_helpers import _news, _upload_png


# ------------------------------- blocks -------------------------------
def test_blocks_crud_and_types(api):
    n = _news(api)
    base = f"/api/admin/news/{n['id']}/blocks"
    t = api.post(base, json={"type": "text", "text": "Сайн уу"})
    assert t.status_code == 201
    t = t.get_json()
    assert t["sort_order"] == 1 and t["text"] == "Сайн уу"
    assert "url" not in t
    img = api.post(base, json={"type": "image", "url": "https://x/a.png", "caption": "c"}).get_json()
    assert img["sort_order"] == 2 and img["caption"] == "c"
    vid = api.post(base, json={"type": "video", "youtube_url": "https://youtu.be/x"}).get_json()
    assert vid["url"] == vid["youtube_url"] == "https://youtu.be/x"
    f = api.post(base, json={"type": "file", "url": "https://x/a.pdf", "name": "a.pdf",
                             "mime_type": "application/pdf", "size": 10}).get_json()
    assert f["name"] == "a.pdf"
    ln = api.post(base, json={"type": "link", "url": "https://x", "title": "X"}).get_json()
    assert ln["title"] == "X"

    lst = api.get(base).get_json()
    assert [b["id"] for b in lst] == [t["id"], img["id"], vid["id"], f["id"], ln["id"]]
    assert [b["id"] for b in api.get(base + "?type=image").get_json()] == [img["id"]]
    assert len(api.get(f"/api/admin/news/{n['id']}").get_json()["blocks"]) == 5

    g = api.get(f"/api/admin/news_blocks/{t['id']}")
    assert g.status_code == 200 and g.get_json()["text"] == "Сайн уу"


@pytest.mark.parametrize("body", [
    {},
    {"type": "gallery"},
    {"type": "image"},
    {"type": "video"},
    {"type": "link", "title": "no url"},
])
def test_block_create_validation(api, body):
    n = _news(api)
    assert api.post(f"/api/admin/news/{n['id']}/blocks", json=body).status_code == 400


def test_block_on_missing_news(api):
    assert api.post("/api/admin/news/999999/blocks",
                    json={"type": "text", "text": "a"}).status_code == 404
    assert api.get("/api/admin/news/999999/blocks").status_code == 404


@pytest.mark.parametrize("method", ["put", "patch"])
def test_block_update(api, method):
    n = _news(api)
    b = api.post(f"/api/admin/news/{n['id']}/blocks",
                 json={"type": "video", "url": "https://youtu.be/a"}).get_json()
    url = f"/api/admin/news_blocks/{b['id']}"
    r = getattr(api, method)(url, json={"youtube_url": "https://youtu.be/b", "title": "T"})
    assert r.status_code == 200
    assert r.get_json()["url"] == "https://youtu.be/b"
    assert r.get_json()["title"] == "T"
    # төрөлд хамаарахгүй талбар л ирвэл 400
    assert getattr(api, method)(url, json={"text": "x"}).status_code == 400
    assert getattr(api, method)("/api/admin/news_blocks/999999",
                                json={"title": "x"}).status_code == 404


def test_block_delete(api):
    n = _news(api)
    b = api.post(f"/api/admin/news/{n['id']}/blocks",
                 json={"type": "text", "text": "a"}).get_json()
    r = api.delete(f"/api/admin/news_blocks/{b['id']}")
    assert r.status_code == 200 and r.get_json() == {"deleted": b["id"]}
    assert api.get(f"/api/admin/news_blocks/{b['id']}").status_code == 404
    assert api.delete(f"/api/admin/news_blocks/{b['id']}").status_code == 404


def test_block_delete_removes_uploaded_file(api, anon):
    url = _upload_png(api)
    n = _news(api)
    b = api.post(f"/api/admin/news/{n['id']}/blocks",
                 json={"type": "image", "url": url}).get_json()
    api.delete(f"/api/admin/news_blocks/{b['id']}")
    assert anon.get(url).status_code == 404


@pytest.mark.parametrize("method", ["put", "patch"])
def test_blocks_reorder(api, method):
    n = _news(api)
    base = f"/api/admin/news/{n['id']}/blocks"
    a = api.post(base, json={"type": "text", "text": "a"}).get_json()
    b = api.post(base, json={"type": "text", "text": "b"}).get_json()
    r = getattr(api, method)(base + "/reorder", json={"order": [
        {"id": a["id"], "sort_order": 2}, {"id": b["id"], "sort_order": 1}]})
    assert r.status_code == 200
    assert r.get_json() == {"updated": [a["id"], b["id"]]}
    assert [x["id"] for x in api.get(base).get_json()] == [b["id"], a["id"]]


def test_blocks_reorder_validation(api):
    n = _news(api)
    other = _news(api)
    ob = api.post(f"/api/admin/news/{other['id']}/blocks",
                  json={"type": "text", "text": "x"}).get_json()
    url = f"/api/admin/news/{n['id']}/blocks/reorder"
    assert api.put(url, json={}).status_code == 400
    assert api.put(url, json={"order": []}).status_code == 400
    assert api.put(url, json={"order": [{"sort_order": 1}]}).status_code == 400
    assert api.put(url, json={"order": [{"id": ob["id"], "sort_order": 1}]}).status_code == 404
    assert api.put("/api/admin/news/999999/blocks/reorder",
                   json={"order": [{"id": 1}]}).status_code == 404


# ------------------------------- portal -------------------------------
def test_portal_only_published_and_token_free(api, anon):
    tag = uniq("prt")
    draft = _news(api, title=f"{tag} draft")
    pub = _news(api, title=f"{tag} pub", status="published")
    api.post(f"/api/admin/news/{pub['id']}/blocks", json={"type": "text", "text": "body"})

    r = anon.get(f"/api/portal/news?search={tag}")
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) == {"data", "total", "per_page", "current_page", "pages"}
    assert [x["id"] for x in body["data"]] == [pub["id"]]
    assert body["per_page"] == 12

    d = anon.get(f"/api/portal/news/{pub['id']}")
    assert d.status_code == 200
    assert [b["text"] for b in d.get_json()["blocks"]] == ["body"]
    assert anon.get(f"/api/portal/news/{draft['id']}").status_code == 404
    assert anon.get("/api/portal/news/999999").status_code == 404


def test_portal_category_filter(api, anon):
    tag = uniq("cat")
    a = _news(api, title=f"{tag} a", category="Мэдээ", status="published")
    b = _news(api, title=f"{tag} b", category="Сургалт", status="published")
    r = anon.get("/api/portal/news", query_string={"search": tag, "category": "Сургалт"})
    assert [x["id"] for x in r.get_json()["data"]] == [b["id"]]
    r = anon.get("/api/portal/news", query_string={"search": tag, "category": "Мэдээ"})
    assert [x["id"] for x in r.get_json()["data"]] == [a["id"]]
    r = anon.get("/api/portal/news", query_string={"search": tag})
    assert {x["id"] for x in r.get_json()["data"]} == {a["id"], b["id"]}
    assert anon.get("/api/portal/news", query_string={"category": "Спорт"}).status_code == 400


def test_portal_paging_validation(anon):
    assert anon.get("/api/portal/news?page=x").status_code == 400
    assert anon.get("/api/portal/news?per_page=500").get_json()["per_page"] == 100


def test_portal_hides_unpublished_after_unpublish(api, anon):
    n = _news(api, status="published")
    assert anon.get(f"/api/portal/news/{n['id']}").status_code == 200
    api.put(f"/api/admin/news/{n['id']}", json={"status": "draft"})
    assert anon.get(f"/api/portal/news/{n['id']}").status_code == 404
