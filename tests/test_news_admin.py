"""Мэдээ, зар — /api/admin/news..., /api/admin/news_blocks/..., /api/portal/news — news CRUD, news list."""

import time

import pytest

from conftest import uniq

from _news_helpers import _news, _upload_png


# ------------------------------- news CRUD -------------------------------
def test_create_news_defaults_to_draft(api):
    n = _news(api, author="Бат")
    assert n["status"] == "draft"
    assert n["published_at"] is None
    assert n["blocks"] == []
    assert n["author"] == "Бат"
    assert n["category"] == "Мэдээ"


def test_create_news_published_stamps_date(api):
    n = _news(api, status="published")
    assert n["status"] == "published"
    assert n["published_at"]


@pytest.mark.parametrize("body", [
    {},
    {"title": "x"},
    {"category": "Мэдээ"},
    {"title": "x", "category": "Спорт"},
    {"title": "x", "category": "Мэдээ", "status": "archived"},
])
def test_create_news_validation(api, body):
    assert api.post("/api/admin/news", json=body).status_code == 400


def test_create_news_requires_token(anon):
    r = anon.post("/api/admin/news", json={"title": "x", "category": "Мэдээ"})
    assert r.status_code == 401


def test_get_news_and_404(api):
    n = _news(api)
    r = api.get(f"/api/admin/news/{n['id']}")
    assert r.status_code == 200
    assert r.get_json()["title"] == n["title"]
    assert r.get_json()["blocks"] == []
    assert api.get("/api/admin/news/999999").status_code == 404


@pytest.mark.parametrize("method", ["put", "patch"])
def test_update_news(api, method):
    n = _news(api)
    r = getattr(api, method)(f"/api/admin/news/{n['id']}",
                             json={"title": "Шинэ гарчиг", "category": "Сургалт"})
    assert r.status_code == 200, r.get_json()
    out = r.get_json()
    assert out["title"] == "Шинэ гарчиг"
    assert out["category"] == "Сургалт"
    assert out["summary"] == "товч"           # хэсэгчилсэн засвар


def test_update_news_validation(api):
    n = _news(api)
    url = f"/api/admin/news/{n['id']}"
    assert api.put(url, json={"category": "Буруу"}).status_code == 400
    assert api.put(url, json={"status": "archived"}).status_code == 400
    assert api.put(url, json={"foo": 1}).status_code == 400
    assert api.put(url, data="not json", content_type="application/json").status_code == 400
    assert api.put("/api/admin/news/999999", json={"title": "x"}).status_code == 404


def test_publish_keeps_first_published_at(api):
    n = _news(api)
    url = f"/api/admin/news/{n['id']}"
    first = api.put(url, json={"status": "published"}).get_json()["published_at"]
    assert first
    assert api.put(url, json={"status": "draft"}).get_json()["published_at"] == first
    time.sleep(1.1)
    again = api.put(url, json={"status": "published"}).get_json()
    assert again["status"] == "published"
    assert again["published_at"] == first


def test_delete_news_cascades_blocks(api):
    n = _news(api)
    b = api.post(f"/api/admin/news/{n['id']}/blocks",
                 json={"type": "text", "text": "a"}).get_json()
    r = api.delete(f"/api/admin/news/{n['id']}")
    assert r.status_code == 200
    assert r.get_json() == {"deleted": n["id"]}
    assert api.get(f"/api/admin/news/{n['id']}").status_code == 404
    assert api.get(f"/api/admin/news_blocks/{b['id']}").status_code == 404
    assert api.delete(f"/api/admin/news/{n['id']}").status_code == 404


def test_cover_replace_and_delete_remove_files(api, anon):
    old = _upload_png(api)
    n = _news(api, cover_image_url=old)
    assert anon.get(old).status_code == 200
    new = _upload_png(api)
    r = api.patch(f"/api/admin/news/{n['id']}", json={"cover_image_url": new})
    assert r.get_json()["cover_image_url"] == new
    assert anon.get(old).status_code == 404        # хуучин ковер дискнээс арилсан
    assert anon.get(new).status_code == 200
    api.delete(f"/api/admin/news/{n['id']}")
    assert anon.get(new).status_code == 404


# ------------------------------- news list -------------------------------
def test_admin_list_shape_search_and_paging(api):
    tag = uniq("srch")
    ids = [_news(api, title=f"{tag} {i}")["id"] for i in range(3)]
    r = api.get(f"/api/admin/news?search={tag}&per_page=2")
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) == {"data", "total", "per_page", "current_page", "pages"}
    assert body["total"] == 3
    assert body["per_page"] == 2
    assert body["current_page"] == 1
    assert body["pages"] == 2
    assert len(body["data"]) == 2
    page2 = api.get(f"/api/admin/news?search={tag}&per_page=2&page=2").get_json()
    assert page2["current_page"] == 2
    assert len(page2["data"]) == 1
    got = {d["id"] for d in body["data"]} | {d["id"] for d in page2["data"]}
    assert got == set(ids)


def test_admin_list_filters(api):
    tag = uniq("flt")
    d = _news(api, title=f"{tag} a", category="Мэдээ")
    p = _news(api, title=f"{tag} b", category="Сургалт", status="published")
    r = api.get(f"/api/admin/news?search={tag}&status=published").get_json()
    assert [x["id"] for x in r["data"]] == [p["id"]]
    r = api.get("/api/admin/news", query_string={"search": tag, "category": "Мэдээ"}).get_json()
    assert [x["id"] for x in r["data"]] == [d["id"]]


def test_admin_list_per_page_cap_and_bad_page(api):
    assert api.get("/api/admin/news?per_page=1000").get_json()["per_page"] == 100
    assert api.get("/api/admin/news?page=abc").status_code == 400
    assert api.get("/api/admin/news?per_page=x").status_code == 400
