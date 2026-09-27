"""Порталын хайлт — client/search.py + core/search_core.py (токенгүй)."""
import pytest

import client.search as search_mod
from conftest import uniq
from _content_helpers import _menu
from _forms_helpers import published_form, make_form
from _news_helpers import _news


@pytest.fixture(autouse=True)
def fresh():
    search_mod.reset_state()
    yield
    search_mod.reset_state()


def kw():
    """Бусад тесттэй давхцахгүй кирилл түлхүүр үг (Том үсгээр эхэлнэ)."""
    return uniq("Зэгсхайлт")


def _suggest(anon, q, **params):
    r = anon.get("/api/portal/search/suggest", query_string={"q": q, **params})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["items"]


def _search(anon, q, **params):
    r = anon.get("/api/portal/search", query_string={"q": q, **params})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _published_page(api, parent=None, visible=True, status="published", body=None):
    m = _menu(api, type="page", parent_id=parent, is_visible=visible)
    pid = m["page_id"]
    r = api.put(f"/api/page/{pid}", json={"status": status, "body": body})
    assert r.status_code == 200, r.get_json()
    return m, pid


# ============================== suggest ==============================
def test_suggest_order_case_and_shape(api, anon):
    k = kw()
    a = _news(api, title=f"Тухай {k}", status="published")
    b = _news(api, title=f"{k} эхэлсэн", status="published")
    items = _suggest(anon, k.lower())                        # жижиг үсгээр — кирилл
    ids = [i["id"] for i in items if i["type"] == "news"]
    assert ids[:2] == [b["id"], a["id"]]                     # эхэлсэн нь түрүүнд
    assert items[0] == {"type": "news", "id": b["id"], "title": f"{k} эхэлсэн",
                        "path": f"/news/{b['id']}", "anchor": None}


def test_suggest_limit_and_bad_q(anon, api):
    k = kw()
    for i in range(3):
        _news(api, title=f"{k} {i}", status="published")
    assert len(_suggest(anon, k, limit=2)) == 2
    assert _suggest(anon, "а") == []                         # < 2 тэмдэгт
    assert _suggest(anon, "x" * 61) == []                    # > 60
    assert _suggest(anon, "   ") == []
    assert anon.get("/api/portal/search/suggest?q=ab&limit=z").status_code == 400


def test_only_visible_content(api, anon):
    k = kw()
    _news(api, title=f"{k} ноорог")                          # draft мэдээ
    _published_page(api, visible=False)                      # нуусан цэс
    hidden_parent = _menu(api, type="page", is_visible=False)
    child, _ = _published_page(api, parent=hidden_parent["id"])
    api.put(f"/api/menu/{child['id']}", json={"title": f"{k} нуусан эцэг"})
    m, _ = _published_page(api, status="draft")              # draft хуудас
    api.put(f"/api/menu/{m['id']}", json={"title": f"{k} ноорог хуудас"})
    make_form(api, title=f"{k} ноорог судалгаа")             # draft маягт
    api.post("/api/partner", json={"name": f"{k} нуусан", "url": "https://a.mn",
                                   "is_visible": False})
    assert _suggest(anon, k) == []
    assert _search(anon, k)["total"] == 0


def test_page_path_block_anchor_and_document(api, anon):
    k = kw()
    parent = _menu(api, type="page", title=uniq("Бидний тухай"))
    child, pid = _published_page(api, parent=parent["id"])
    child = api.put(f"/api/menu/{child['id']}", json={"title": f"{k} танилцуулга"}).get_json()
    t = api.post("/api/page_block", json={"page_id": pid, "type": "text",
                                          "text": f"<h2>{k} зорилго</h2><p>текст</p>"}).get_json()
    f = api.post("/api/page_block", json={"page_id": pid, "type": "file", "url": "/uploads/content/x.pdf",
                                          "name": f"{k} журам.pdf"}).get_json()
    items = _suggest(anon, k)
    path = f"/{parent['slug']}/{child['slug']}"
    assert {"type": "page", "id": pid, "title": f"{k} танилцуулга", "path": path,
            "anchor": None} in items
    assert {"type": "page", "id": pid, "title": f"{k} зорилго", "path": path,
            "anchor": f"block-{t['id']}"} in items
    assert {"type": "document", "id": pid, "title": f"{k} журам.pdf", "path": path,
            "anchor": f"block-{f['id']}"} in items


def test_forms_and_partners(api, anon):
    k = kw()
    sid, _ = published_form(api, title=f"{k} сэтгэл ханамж")
    pid, _ = published_form(api, title=f"{k} санал", type="poll")
    par = api.post("/api/partner", json={"name": f"{k} яам", "url": "https://moe.gov.mn"}).get_json()
    items = _suggest(anon, k)
    assert {"type": "survey", "id": sid, "title": f"{k} сэтгэл ханамж", "path": f"/survey/{sid}",
            "anchor": None} in items
    assert any(i["type"] == "poll" and i["path"] == f"/poll/{pid}" for i in items)
    assert {"type": "partner", "id": par["id"], "title": f"{k} яам",
            "path": "https://moe.gov.mn", "anchor": None} in items


# ============================== search ==============================
def test_search_body_snippet_and_ranking(api, anon):
    k = kw()
    body_hit = _news(api, title=uniq("Энгийн гарчиг"), status="published",
                     summary=("урт " * 60) + f"{k.lower()} дунд нь " + ("төгсгөл " * 60))
    title_hit = _news(api, title=f"{k} гарчигт", status="published")
    d = _search(anon, k)
    ids = [i["id"] for i in d["items"]]
    assert ids.index(title_hit["id"]) < ids.index(body_hit["id"])   # гарчиг -> их бие
    item = next(i for i in d["items"] if i["id"] == body_hit["id"])
    assert f"<mark>{k.lower()}</mark>" in item["snippet"]
    assert item["snippet"].startswith("…") and item["snippet"].endswith("…")
    assert len(item["snippet"]) <= 160 + len("<mark></mark>") + 2
    assert set(item) == {"type", "id", "title", "path", "anchor", "snippet"}


def test_search_page_block_text_and_html_escaped(api, anon):
    k = kw()
    _, pid = _published_page(api)
    b = api.post("/api/page_block", json={"page_id": pid, "type": "text",
                                          "text": f"<p>&lt;script&gt; {k} энд</p>"}).get_json()
    d = _search(anon, k)
    item = next(i for i in d["items"] if i["anchor"] == f"block-{b['id']}")
    assert item["type"] == "page" and item["title"]            # гарчиггүй блок -> хуудасны гарчиг
    assert "&lt;script&gt;" in item["snippet"] and "<script>" not in item["snippet"]


def test_search_type_filter_and_paging(api, anon):
    k = kw()
    for i in range(3):
        _news(api, title=f"{k} {i}", status="published")
    published_form(api, title=f"{k} судалгаа")
    assert _search(anon, k, type="survey")["total"] == 1
    d = _search(anon, k, type="news", per_page=2, page=2)
    assert (d["total"], d["pages"], d["page"], d["per_page"], len(d["items"])) == (3, 2, 2, 2, 1)
    assert anon.get("/api/portal/search?q=abc&type=bad").status_code == 400
    assert anon.get("/api/portal/search?q=abc&page=x").status_code == 400
    assert _search(anon, "а") == {"items": [], "page": 1, "pages": 0, "per_page": 10, "total": 0}


def test_wildcards_are_literal(api, anon):
    _news(api, title=uniq("Энгийн"), status="published")
    assert _search(anon, "%%")["total"] == 0
    assert _suggest(anon, "__") == []


# ============================ public / limits ============================
def test_public_cache_header_and_result_cache(api, anon):
    k = kw()
    r = anon.get("/api/portal/search/suggest", query_string={"q": k})
    assert r.status_code == 200 and r.headers["Cache-Control"] == "public, max-age=60"
    assert r.get_json()["items"] == []
    _news(api, title=f"{k} шинэ", status="published")
    assert _suggest(anon, k) == []                           # 60 сек кэш
    search_mod.reset_state()
    assert len(_suggest(anon, k)) == 1


def test_rate_limit_per_ip(anon, monkeypatch):
    monkeypatch.setattr(search_mod, "RATE_LIMIT", 3)
    h = {"X-Real-IP": "198.51.100.7"}
    codes = [anon.get("/api/portal/search?q=ab", headers=h).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = anon.get("/api/portal/search/suggest?q=ab", headers=h)
    assert r.status_code == 429 and "error" in r.get_json()
    assert anon.get("/api/portal/search?q=ab", headers={"X-Real-IP": "198.51.100.8"}).status_code == 200


def test_index_refreshes_immediately_on_change(api, anon):
    """Нэмэх/устгах нь хээг (COUNT) өөрчилдөг тул индекс тэр даруй шинэчлэгдэнэ."""
    k = kw()
    assert _suggest(anon, k) == []                           # индекс баригдсан
    n = _news(api, title=f"{k} шинэ", status="published")
    assert [i["id"] for i in _suggest(anon, f"{k} ш")] == [n["id"]]      # өөр q — кэшгүй
    api.delete(f"/api/admin/news/{n['id']}")
    assert _suggest(anon, f"{k} ши") == []                   # устгамагц алга


def test_same_second_edit_caught_by_max_age(api, anon, monkeypatch):
    """Нэг секундэд хоёр засвар хээг өөрчлөхгүй — CORPUS_MAX_AGE хуучин индексийг дахин барина."""
    k = kw()
    n = _news(api, title=f"{k} нуух", status="published")
    assert len(_suggest(anon, k)) == 1
    api.put(f"/api/admin/news/{n['id']}", json={"status": "draft"})   # ижил секунд байж болно
    import core.search_core as sc
    monkeypatch.setattr(sc, "CORPUS_MAX_AGE", 0)
    assert _suggest(anon, f"{k} н") == []
