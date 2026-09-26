"""Санал хүсэлт / Өргөдөл гомдол — /api/portal/suggestions|complaints (токенгүй)
ба /api/admin/suggestions|complaints (жагсаалт + устгал)."""
import io

import pytest

from conftest import uniq, PNG_BYTES

TEXT = {"suggestions": "message", "complaints": "description"}


def _body(kind, **kw):
    body = {"name": "Бат", "email": "bat@example.mn", "phone": "99112233",
            TEXT[kind]: "Текст"}
    body.update(kw)
    return body


def _submit(anon, kind, **kw):
    r = anon.post(f"/api/portal/{kind}", json=_body(kind, **kw))
    assert r.status_code == 201, r.get_json()
    return r.get_json()


# ------------------------------- portal -------------------------------
@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_submit_token_free(anon, kind):
    out = _submit(anon, kind)
    assert out["status"] is True
    assert isinstance(out["id"], int)
    assert "бүртгэгдлээ" in out["message"]


def test_complaint_with_attachment(api, anon):
    tag = uniq("att")
    out = _submit(anon, "complaints", name=tag, file_url="https://x/a.pdf", file_name="a.pdf")
    items = api.get(f"/api/admin/complaints?search={tag}").get_json()["items"]
    assert len(items) == 1
    row = items[0]
    assert row["id"] == out["id"]
    assert row["file_url"] == "https://x/a.pdf" and row["file_name"] == "a.pdf"
    assert row["status"] == "new"
    assert row["description"] == "Текст"


@pytest.mark.parametrize("phone", ["99112233", "+976 9911 2233", "976-9911-2233",
                                   "(9911) 2233", "+97699112233"])
def test_phone_accepted_formats(anon, phone):
    _submit(anon, "suggestions", phone=phone)


@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
@pytest.mark.parametrize("override", [
    {"name": ""},
    {"name": "   "},
    {"name": None},
    {"email": ""},
    {"phone": ""},
    {"email": "not-an-email"},
    {"email": "a@b"},
    {"email": "a b@c.mn"},
    {"phone": "9911223"},
    {"phone": "991122334"},
    {"phone": "9911abcd"},
    {"phone": "+976 991122"},
    {"name": "x" * 201},
    {"email": "a" * 251 + "@x.mn"},
])
def test_validation_rejects(anon, kind, override):
    r = anon.post(f"/api/portal/{kind}", json=_body(kind, **override))
    assert r.status_code == 400, r.get_json()
    assert "error" in r.get_json()


@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_missing_text_field_and_no_body(anon, kind):
    body = _body(kind)
    del body[TEXT[kind]]
    assert anon.post(f"/api/portal/{kind}", json=body).status_code == 400
    assert anon.post(f"/api/portal/{kind}").status_code == 400
    assert anon.post(f"/api/portal/{kind}", json=[1, 2]).status_code == 400


def test_complaint_file_length_limits(anon):
    r = anon.post("/api/portal/complaints",
                  json=_body("complaints", file_name="f" * 256))
    assert r.status_code == 400
    r = anon.post("/api/portal/complaints",
                  json=_body("complaints", file_url="https://x/" + "a" * 2000))
    assert r.status_code == 400


def test_limits_are_inclusive(anon):
    _submit(anon, "suggestions", name="x" * 200)


# ------------------------------- admin -------------------------------
@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_admin_list_requires_token(anon, kind):
    assert anon.get(f"/api/admin/{kind}").status_code == 401


@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_admin_list_shape_search_paging(api, anon, kind):
    tag = uniq("fb")
    ids = [_submit(anon, kind, name=f"{tag} {i}")["id"] for i in range(3)]
    r = api.get(f"/api/admin/{kind}?search={tag}&per_page=2")
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) == {"items", "total", "page", "per_page", "pages"}
    assert body["total"] == 3 and body["pages"] == 2 and body["page"] == 1
    assert [x["id"] for x in body["items"]] == sorted(ids, reverse=True)[:2]   # шинэ нь дээрээ
    assert TEXT[kind] in body["items"][0]
    p2 = api.get(f"/api/admin/{kind}?search={tag}&per_page=2&page=2").get_json()
    assert [x["id"] for x in p2["items"]] == [min(ids)]


@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_admin_search_by_text_and_email(api, anon, kind):
    tag = uniq("body")
    out = _submit(anon, kind, **{TEXT[kind]: f"агуулга {tag}", "email": f"{tag}@x.mn"})
    for q in (f"агуулга {tag}", f"{tag}@x.mn"):
        items = api.get(f"/api/admin/{kind}", query_string={"search": q}).get_json()["items"]
        assert [x["id"] for x in items] == [out["id"]]


@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_admin_list_per_page_cap_and_bad_numbers(api, kind):
    assert api.get(f"/api/admin/{kind}?per_page=1000").get_json()["per_page"] == 100
    assert api.get(f"/api/admin/{kind}?per_page=0").get_json()["per_page"] == 1
    assert api.get(f"/api/admin/{kind}?page=abc").status_code == 400
    assert api.get(f"/api/admin/{kind}?per_page=x").status_code == 400


@pytest.mark.parametrize("kind", ["suggestions", "complaints"])
def test_admin_delete(api, anon, kind):
    tag = uniq("del")
    out = _submit(anon, kind, name=tag)
    r = api.delete(f"/api/admin/{kind}/{out['id']}")
    assert r.status_code == 200 and r.get_json() == {"deleted": out["id"]}
    assert api.get(f"/api/admin/{kind}?search={tag}").get_json()["total"] == 0
    assert api.delete(f"/api/admin/{kind}/{out['id']}").status_code == 404


def test_complaint_delete_removes_uploaded_file(api, anon):
    up = api.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "a.png")},
                  content_type="multipart/form-data").get_json()
    out = _submit(anon, "complaints", file_url=up["url"], file_name="a.png")
    assert anon.get(up["url"]).status_code == 200
    api.delete(f"/api/admin/complaints/{out['id']}")
    assert anon.get(up["url"]).status_code == 404


def test_admin_no_get_one_route(api, anon):
    out = _submit(anon, "suggestions")
    assert api.get(f"/api/admin/suggestions/{out['id']}").status_code == 405


def test_admin_permission_required(make_user):
    u, _ = make_user(["suggestion.read"])
    assert u.get("/api/admin/suggestions").status_code == 200
    assert u.get("/api/admin/complaints").status_code == 403
    assert u.delete("/api/admin/suggestions/999999").status_code == 403
