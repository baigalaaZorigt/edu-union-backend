"""admin/content.py — порталын цэс, контент хуудас, блок, файл байршуулалт — page_image / page_file / page_video, upload."""

import io
import os

from conftest import PDF_BYTES, PNG_BYTES
import admin.content as content

from _content_helpers import _disk_path, _page_menu, _upload


# ============== page_image / page_file / page_video ==============
def test_page_image_typed_view(api):
    m, page_id = _page_menu(api)
    url = _upload(api).get_json()["url"]
    r = api.post("/api/page_image", json={"page_id": page_id, "url": url, "caption": "cap"})
    assert r.status_code == 201
    img = r.get_json()
    assert img["type"] == "image" and img["caption"] == "cap"
    assert api.post("/api/page_image", json={"page_id": page_id}).status_code == 400
    assert api.post("/api/page_image", json={"page_id": 999999, "url": "x"}).status_code == 400
    assert [x["id"] for x in api.get(f"/api/page_image?page_id={page_id}").get_json()] == [img["id"]]
    assert img["id"] in {x["id"] for x in api.get("/api/page_image").get_json()}
    # өөр төрлийн блокийг энэ замаар устгаж болохгүй
    txt = api.post("/api/page_block", json={"page_id": page_id, "type": "text", "text": "t"}).get_json()
    assert api.delete(f"/api/page_image/{txt['id']}").status_code == 404
    assert api.delete(f"/api/page_image/{img['id']}").get_json() == {"deleted": img["id"]}
    assert os.path.exists(_disk_path(url))                 # soft delete — файл үлдэнэ
    api.delete(f"/api/menu/{m['id']}")


def test_page_file_typed_view(api):
    m, page_id = _page_menu(api)
    r = api.post("/api/page_file", json={"page_id": page_id, "url": "/uploads/content/none.pdf",
                                         "name": "Журам.pdf", "mime_type": "application/pdf",
                                         "size": 123})
    assert r.status_code == 201
    f = r.get_json()
    assert f["name"] == "Журам.pdf" and f["size"] == 123
    assert api.post("/api/page_file", json={"page_id": page_id, "url": "x"}).status_code == 400
    assert [x["id"] for x in api.get(f"/api/page_file?page_id={page_id}").get_json()] == [f["id"]]
    assert f["id"] in {x["id"] for x in api.get("/api/page_file").get_json()}
    assert api.delete(f"/api/page_video/{f['id']}").status_code == 404
    assert api.delete(f"/api/page_file/{f['id']}").status_code == 200
    assert api.delete(f"/api/page_file/{f['id']}").status_code == 404
    api.delete(f"/api/menu/{m['id']}")


def test_page_video_typed_view(api):
    m, page_id = _page_menu(api)
    r = api.post("/api/page_video", json={"page_id": page_id, "title": "V",
                                          "youtube_url": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 201
    v = r.get_json()
    assert v["youtube_url"] == v["url"] == "https://www.youtube.com/watch?v=abc"
    assert api.post("/api/page_video", json={"page_id": page_id,
                                             "youtube_url": "https://vimeo.com/1"}).status_code == 400
    assert api.post("/api/page_video", json={"page_id": page_id}).status_code == 400
    assert [x["id"] for x in api.get(f"/api/page_video?page_id={page_id}").get_json()] == [v["id"]]
    assert v["id"] in {x["id"] for x in api.get("/api/page_video").get_json()}
    assert api.delete(f"/api/page_video/{v['id']}").status_code == 200
    api.delete(f"/api/menu/{m['id']}")


# ============================ upload ============================
def test_upload_image_and_serve_without_token(api, anon):
    r = _upload(api, "Лого.PNG")
    assert r.status_code == 201
    up = r.get_json()
    assert up["url"].startswith("/uploads/content/") and up["url"].endswith(".png")
    assert up["name"] == "Лого.PNG" and up["mime_type"] == "image/png"
    assert up["size"] == len(PNG_BYTES)
    got = anon.get(up["url"])
    assert got.status_code == 200 and got.data == PNG_BYTES
    assert anon.get("/uploads/content/missing.png").status_code == 404
    content.remove_upload(up["url"])


def test_upload_documents(api):
    for name, mime in (("a.pdf", "application/pdf"), ("a.docx", content.DOC_TYPES["docx"]),
                       ("a.xls", "application/vnd.ms-excel")):
        r = _upload(api, name, PDF_BYTES)
        assert r.status_code == 201, name
        assert r.get_json()["mime_type"] == mime
        content.remove_upload(r.get_json()["url"])


def test_upload_validation(api, anon):
    assert api.post("/api/upload", data={}, content_type="multipart/form-data").status_code == 400
    assert _upload(api, "a.exe", b"MZ").status_code == 400
    assert _upload(api, "noext", b"x").status_code == 400
    assert _upload(api, "empty.png", b"").status_code == 400
    big_img = b"\0" * (content.MAX_IMAGE_SIZE + 1)
    assert _upload(api, "big.jpg", big_img).status_code == 400
    # 5 MB-аас том ч 20 MB-аас бага баримт бичиг зөвшөөрөгдөнө
    r = _upload(api, "big.pdf", big_img)
    assert r.status_code == 201
    content.remove_upload(r.get_json()["url"])
    # токенгүй байршуулах боломжгүй
    r = anon.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "a.png")},
                  content_type="multipart/form-data")
    assert r.status_code == 401


def test_remove_upload_ignores_external_urls():
    content.remove_upload("https://example.mn/a.png")     # алдаа гаргахгүй
    content.remove_upload(None)
    content.remove_upload("/uploads/content/does-not-exist.png")
