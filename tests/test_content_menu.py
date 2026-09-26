"""admin/content.py — порталын цэс, контент хуудас, блок, файл байршуулалт — menu."""

import os

from conftest import uniq

from _content_helpers import _disk_path, _menu, _page_menu, _upload


# ============================ menu ============================
def test_menu_requires_token(anon):
    assert anon.get("/api/menu").status_code == 401


def test_menu_requires_permission(make_user):
    u, _ = make_user(["member.read"])
    assert u.get("/api/menu").status_code == 403
    assert u.post("/api/menu", json={"title": "x"}).status_code == 403


def test_menu_create_defaults_to_page_and_autocreates_page(api):
    m = _menu(api, title="Бидний тухай тест")
    assert m["type"] == "page"
    assert m["is_visible"] == 1
    assert m["slug"].startswith("bidnii-tuhai-test")
    assert m["page_id"]
    r = api.get(f"/api/page/{m['id']}")
    assert r.status_code == 200
    page = r.get_json()
    assert page["id"] == m["page_id"]
    assert page["status"] == "draft"
    assert page["blocks"] == [] and page["images"] == []
    api.delete(f"/api/menu/{m['id']}")


def test_menu_slug_unique_suffix(api):
    title = uniq("Давхар ")
    a = _menu(api, title=title)
    b = _menu(api, title=title)
    assert b["slug"] == a["slug"] + "-2"
    c = _menu(api, title="x", slug=a["slug"])        # гараар өгсөн slug ч давхцвал
    assert c["slug"] == a["slug"] + "-3"
    for m in (a, b, c):
        api.delete(f"/api/menu/{m['id']}")


def test_menu_create_validation(api):
    assert api.post("/api/menu", json={}).status_code == 400
    assert api.post("/api/menu", json={"type": "page"}).status_code == 400   # title алга
    assert api.post("/api/menu", json={"title": "x", "type": "bogus"}).status_code == 400
    assert api.post("/api/menu", json={"title": "x", "type": "external"}).status_code == 400
    assert api.post("/api/menu", json={"title": "x", "parent_id": "abc"}).status_code == 400
    assert api.post("/api/menu", json={"title": "x", "parent_id": 999999}).status_code == 400


def test_menu_external_and_non_page_types_have_no_page(api):
    m = _menu(api, type="external", external_url="https://example.mn")
    assert m["external_url"] == "https://example.mn"
    assert m["page_id"] is None
    assert api.get(f"/api/page/{m['id']}").status_code == 404
    api.delete(f"/api/menu/{m['id']}")


def test_menu_news_category_rules(api):
    m = _menu(api, type="news", news_category="Сургалт")
    assert m["news_category"] == "Сургалт"
    assert api.post("/api/menu", json={"title": "x", "type": "news",
                                       "news_category": "Спорт"}).status_code == 400
    assert api.post("/api/menu", json={"title": "x", "type": "page",
                                       "news_category": "Мэдээ"}).status_code == 400
    r = api.patch(f"/api/menu/{m['id']}", json={"news_category": ""})   # хоосон = бүгд
    assert r.status_code == 200 and r.get_json()["news_category"] is None
    lst = api.get("/api/menu?type=news").get_json()
    assert any(x["id"] == m["id"] for x in lst)
    api.delete(f"/api/menu/{m['id']}")


def test_menu_depth_limited_to_two_levels(api):
    root = _menu(api)
    child = _menu(api, parent_id=root["id"])
    assert child["parent_id"] == root["id"]
    assert child["sort_order"] == 1
    r = api.post("/api/menu", json={"title": "grand", "parent_id": child["id"]})
    assert r.status_code == 400
    # өөрийгөө эцэг болгох / дэд цэстэй цэсийг өөр доор оруулах хориотой
    assert api.put(f"/api/menu/{root['id']}", json={"parent_id": root["id"]}).status_code == 400
    other = _menu(api)
    assert api.put(f"/api/menu/{root['id']}", json={"parent_id": other["id"]}).status_code == 400
    api.delete(f"/api/menu/{root['id']}")
    api.delete(f"/api/menu/{other['id']}")


def test_menu_list_filters_and_tree(api):
    root = _menu(api, is_visible=False)
    child = _menu(api, parent_id=root["id"])
    flat = api.get("/api/menu").get_json()
    assert {root["id"], child["id"]} <= {m["id"] for m in flat}
    kids = api.get(f"/api/menu?parent_id={root['id']}").get_json()
    assert [k["id"] for k in kids] == [child["id"]]
    roots = api.get("/api/menu?parent_id=null").get_json()
    assert all(m["parent_id"] is None for m in roots)
    hidden = api.get("/api/menu?is_visible=0").get_json()
    assert root["id"] in {m["id"] for m in hidden}
    tree = api.get("/api/menu?tree=1").get_json()
    node = next(n for n in tree if n["id"] == root["id"])
    assert [c["id"] for c in node["children"]] == [child["id"]]
    api.delete(f"/api/menu/{root['id']}")


def test_menu_get_update_put_patch(api):
    m = _menu(api, type="news")
    assert api.get(f"/api/menu/{m['id']}").get_json()["title"] == m["title"]
    assert api.get("/api/menu/999999").status_code == 404
    r = api.put(f"/api/menu/{m['id']}", json={"title": "Шинэ нэр", "is_visible": 0})
    assert r.status_code == 200
    body = r.get_json()
    assert body["title"] == "Шинэ нэр" and body["is_visible"] == 0
    assert body["slug"].startswith("shine-ner")
    r = api.patch(f"/api/menu/{m['id']}", json={"sort_order": 42})
    assert r.status_code == 200 and r.get_json()["sort_order"] == 42
    assert api.put(f"/api/menu/{m['id']}", json={}).status_code == 400
    assert api.put(f"/api/menu/{m['id']}", json={"type": "bad"}).status_code == 400
    assert api.put(f"/api/menu/{m['id']}", json={"type": "external"}).status_code == 400
    assert api.put("/api/menu/999999", json={"title": "x"}).status_code == 404
    # page болгож сольвол хуудас нөхөгдөнө
    assert m["page_id"] is None
    r = api.patch(f"/api/menu/{m['id']}", json={"type": "page"})
    assert r.status_code == 200 and r.get_json()["page_id"]
    api.delete(f"/api/menu/{m['id']}")


def test_menu_reorder(api):
    a, b = _menu(api), _menu(api)
    r = api.put("/api/menu/reorder", json={"order": [
        {"id": a["id"], "parent_id": None, "sort_order": 9},
        {"id": b["id"], "parent_id": a["id"], "sort_order": 1}]})
    assert r.status_code == 200
    assert r.get_json()["updated"] == [a["id"], b["id"]]
    got = api.get(f"/api/menu/{b['id']}").get_json()
    assert got["parent_id"] == a["id"] and got["sort_order"] == 1
    assert api.get(f"/api/menu/{a['id']}").get_json()["sort_order"] == 9
    r = api.patch("/api/menu/reorder", json={"order": [
        {"id": b["id"], "parent_id": None, "sort_order": 2}]})
    assert r.status_code == 200
    assert api.get(f"/api/menu/{b['id']}").get_json()["parent_id"] is None
    # алдаанууд
    assert api.put("/api/menu/reorder", json={}).status_code == 400
    assert api.put("/api/menu/reorder", json={"order": []}).status_code == 400
    assert api.put("/api/menu/reorder", json={"order": [{"x": 1}]}).status_code == 400
    assert api.put("/api/menu/reorder", json={"order": [{"id": 999999}]}).status_code == 404
    child = _menu(api, parent_id=a["id"])
    r = api.put("/api/menu/reorder", json={"order": [
        {"id": b["id"], "parent_id": child["id"], "sort_order": 1}]})
    assert r.status_code == 400                                      # 3 дахь түвшин
    for m in (a, b):
        api.delete(f"/api/menu/{m['id']}")


def test_menu_delete_cascades_children_page_blocks_and_files(api):
    root, page_id = _page_menu(api)
    child = _menu(api, parent_id=root["id"], type="page")
    up = _upload(api).get_json()
    blk = api.post("/api/page_block", json={"page_id": child["page_id"], "type": "image",
                                            "url": up["url"]}).get_json()
    cover = _upload(api).get_json()
    api.put(f"/api/page/{page_id}", json={"cover_image": cover["url"]})
    assert os.path.isfile(_disk_path(up["url"]))
    r = api.delete(f"/api/menu/{root['id']}")
    assert r.status_code == 200 and r.get_json() == {"deleted": root["id"]}
    assert api.get(f"/api/menu/{child['id']}").status_code == 404
    assert api.get(f"/api/page/{root['id']}").status_code == 404
    assert api.get(f"/api/page_block/{blk['id']}").status_code == 404
    assert not os.path.exists(_disk_path(up["url"]))
    assert not os.path.exists(_disk_path(cover["url"]))
    assert api.delete(f"/api/menu/{root['id']}").status_code == 404
