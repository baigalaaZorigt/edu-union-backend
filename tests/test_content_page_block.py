"""admin/content.py — порталын цэс, контент хуудас, блок, файл байршуулалт — page, page_block."""

import os

from _content_helpers import _disk_path, _menu, _page_menu, _upload


# ============================ page ============================
def test_page_list(api):
    m, page_id = _page_menu(api)
    lst = api.get("/api/page").get_json()
    row = next(p for p in lst if p["id"] == page_id)
    assert row["menu_title"] == m["title"] and row["menu_slug"] == m["slug"]
    api.delete(f"/api/menu/{m['id']}")


def test_page_create(api):
    m = _menu(api, type="news")
    # зөвхөн page цэсэнд
    assert api.post("/api/page", json={"menu_id": m["id"]}).status_code == 400
    api.patch(f"/api/menu/{m['id']}", json={"type": "page"})          # хуудас автоматаар
    assert api.post("/api/page", json={"menu_id": m["id"]}).status_code == 409
    assert api.post("/api/page", json={}).status_code == 400
    assert api.post("/api/page", json={"menu_id": 999999}).status_code == 400
    api.delete(f"/api/menu/{m['id']}")


def test_page_create_on_page_menu_without_page(api):
    """Хуудас нь устгагдсан (эсвэл хуучин) page цэсэнд POST /api/page 201 буцаана."""
    from sqlalchemy import delete
    from core.orm import new_session
    from core.orm.models import Page
    m, page_id = _page_menu(api)
    s = new_session()
    s.execute(delete(Page).where(Page.id == page_id))
    s.commit()
    s.close()
    assert api.post("/api/page", json={"menu_id": m["id"], "status": "bad"}).status_code == 400
    r = api.post("/api/page", json={"menu_id": m["id"], "body": "<p>hi</p>",
                                    "status": "published"})
    assert r.status_code == 201
    p = r.get_json()
    assert p["title"] == m["title"] and p["body"] == "<p>hi</p>" and p["status"] == "published"
    api.delete(f"/api/menu/{m['id']}")


def test_page_update_put_patch_and_cover_replacement(api):
    m, page_id = _page_menu(api)
    r = api.put(f"/api/page/{page_id}", json={"title": "T", "body": "B", "status": "published"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "published" and r.get_json()["body"] == "B"
    r = api.patch(f"/api/page/{page_id}", json={"body": "B2"})
    assert r.status_code == 200 and r.get_json()["title"] == "T"
    assert api.put(f"/api/page/{page_id}", json={"status": "bad"}).status_code == 400
    assert api.put(f"/api/page/{page_id}", json={"foo": 1}).status_code == 400
    assert api.put("/api/page/999999", json={"title": "x"}).status_code == 404
    old = _upload(api).get_json()["url"]
    new = _upload(api).get_json()["url"]
    api.put(f"/api/page/{page_id}", json={"cover_image": old})
    api.put(f"/api/page/{page_id}", json={"cover_image": new})
    assert not os.path.exists(_disk_path(old))                        # хуучин арилсан
    assert os.path.isfile(_disk_path(new))
    api.delete(f"/api/menu/{m['id']}")


def test_page_get_by_menu_id_404(api):
    assert api.get("/api/page/999999").status_code == 404


# ============================ page_block ============================
def test_page_block_crud_and_type_fields(api):
    m, page_id = _page_menu(api)
    t = api.post("/api/page_block", json={"page_id": page_id, "type": "text",
                                          "text": "<p>a</p>", "url": "ignored"})
    assert t.status_code == 201
    t = t.get_json()
    assert t["sort_order"] == 1 and t["text"] == "<p>a</p>" and "url" not in t
    v = api.post("/api/page_block", json={"page_id": page_id, "type": "video",
                                          "url": "https://youtu.be/x", "title": "V"}).get_json()
    assert v["youtube_url"] == "https://youtu.be/x" and v["sort_order"] == 2
    f = api.post("/api/page_block", json={"page_id": page_id, "type": "file", "url": "/x.pdf",
                                          "name": "x.pdf", "mime_type": "application/pdf",
                                          "size": 10}).get_json()
    assert f["name"] == "x.pdf" and f["size"] == 10
    ln = api.post("/api/page_block", json={"page_id": page_id, "type": "link",
                                           "url": "https://a.mn", "title": "L"}).get_json()
    assert set(ln) >= {"url", "title"} and "text" not in ln
    # шүүлтүүд
    assert [b["id"] for b in api.get(f"/api/page_block?page_id={page_id}").get_json()] == \
        [t["id"], v["id"], f["id"], ln["id"]]
    assert [b["id"] for b in api.get(f"/api/page_block?page_id={page_id}&type=link")
            .get_json()] == [ln["id"]]
    # нэгийг авах
    assert api.get(f"/api/page_block/{t['id']}").get_json()["text"] == "<p>a</p>"
    assert api.get("/api/page_block/999999").status_code == 404
    # засах — зөвхөн төрлийн талбарууд
    r = api.put(f"/api/page_block/{t['id']}", json={"text": "<p>b</p>", "sort_order": 7})
    assert r.status_code == 200 and r.get_json()["text"] == "<p>b</p>"
    assert r.get_json()["sort_order"] == 7
    r = api.patch(f"/api/page_block/{ln['id']}", json={"title": "L2"})
    assert r.status_code == 200 and r.get_json()["title"] == "L2"
    assert api.put(f"/api/page_block/{t['id']}", json={"url": "x"}).status_code == 400
    assert api.put("/api/page_block/999999", json={"text": "x"}).status_code == 404
    # хуудсанд бүгд харагдана
    page = api.get(f"/api/page/{m['id']}").get_json()
    assert len(page["blocks"]) == 4
    assert [x["id"] for x in page["videos"]] == [v["id"]]
    assert [x["id"] for x in page["files"]] == [f["id"]]
    # устгах
    assert api.delete(f"/api/page_block/{t['id']}").get_json() == {"deleted": t["id"]}
    assert api.delete(f"/api/page_block/{t['id']}").status_code == 404
    api.delete(f"/api/menu/{m['id']}")


def test_page_block_create_validation(api):
    m, page_id = _page_menu(api)
    assert api.post("/api/page_block", json={"page_id": page_id}).status_code == 400
    assert api.post("/api/page_block", json={"page_id": page_id, "type": "gif"}).status_code == 400
    assert api.post("/api/page_block", json={"page_id": page_id, "type": "image"}).status_code == 400
    assert api.post("/api/page_block", json={"page_id": 999999, "type": "text"}).status_code == 400
    assert api.post("/api/page_block", json={"page_id": "abc", "type": "text"}).status_code == 400
    api.delete(f"/api/menu/{m['id']}")


def test_page_block_reorder(api):
    m, page_id = _page_menu(api)
    a = api.post("/api/page_block", json={"page_id": page_id, "type": "text", "text": "a"}).get_json()
    b = api.post("/api/page_block", json={"page_id": page_id, "type": "text", "text": "b"}).get_json()
    r = api.put("/api/page_block/reorder", json={"order": [
        {"id": a["id"], "sort_order": 2}, {"id": b["id"], "sort_order": 1}]})
    assert r.status_code == 200 and r.get_json()["updated"] == [a["id"], b["id"]]
    ids = [x["id"] for x in api.get(f"/api/page_block?page_id={page_id}").get_json()]
    assert ids == [b["id"], a["id"]]
    r = api.patch("/api/page_block/reorder", json={"order": [{"id": a["id"], "sort_order": 0}]})
    assert r.status_code == 200
    assert api.put("/api/page_block/reorder", json={"order": []}).status_code == 400
    assert api.put("/api/page_block/reorder", json={"order": [{"sort_order": 1}]}).status_code == 400
    assert api.put("/api/page_block/reorder",
                   json={"order": [{"id": 999999, "sort_order": 1}]}).status_code == 404
    api.delete(f"/api/menu/{m['id']}")


def test_page_block_url_replacement_removes_old_file(api):
    m, page_id = _page_menu(api)
    old = _upload(api).get_json()["url"]
    new = _upload(api).get_json()["url"]
    blk = api.post("/api/page_block", json={"page_id": page_id, "type": "image",
                                            "url": old}).get_json()
    api.put(f"/api/page_block/{blk['id']}", json={"url": new, "caption": "c"})
    assert not os.path.exists(_disk_path(old))
    assert os.path.isfile(_disk_path(new))
    api.delete(f"/api/page_block/{blk['id']}")
    assert os.path.exists(_disk_path(new))                             # soft delete — файл үлдэнэ
    api.delete(f"/api/menu/{m['id']}")
