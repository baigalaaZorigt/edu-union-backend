"""Судалгаа / санал асуулгын engine — admin/forms.py + client/forms.py + core/forms_core.py — options, _lock_if_answered, documents (PDF), portal: list / detail."""

import io

from conftest import PDF_BYTES

from _forms_helpers import add_q, make_form, opt, published_form, submit


# ============================ options ============================
def test_option_crud(api):
    f = make_form(api)
    q = add_q(api, f["id"], "single_choice")
    url = f"/api/admin/questions/{q['id']}/options"
    lst = api.get(url)
    assert lst.status_code == 200 and len(lst.get_json()) == 3
    assert api.get("/api/admin/questions/999999/options").status_code == 404

    r = api.post(url, json={"label": "Г"})
    assert r.status_code == 201
    o = r.get_json()
    assert o["label"] == "Г" and o["sort_order"] == 4
    assert api.post(url, json={}).status_code == 400
    assert api.post("/api/admin/questions/999999/options", json={"label": "x"}).status_code == 404

    for method in ("PUT", "PATCH"):
        r = api.request(method, f"/api/admin/options/{o['id']}",
                        json={"label": f"Г-{method}", "sort_order": 9})
        assert r.status_code == 200 and r.get_json()["label"] == f"Г-{method}"
    assert api.put(f"/api/admin/options/{o['id']}", json={}).status_code == 400
    assert api.put(f"/api/admin/options/{o['id']}", json={"label": " "}).status_code == 400
    assert api.put("/api/admin/options/999999", json={"label": "x"}).status_code == 404

    r = api.delete(f"/api/admin/options/{o['id']}")
    assert r.status_code == 200 and r.get_json()["deleted"] == o["id"]
    assert api.delete(f"/api/admin/options/{o['id']}").status_code == 404


def test_option_on_non_choice_question(api):
    f = make_form(api)
    q = add_q(api, f["id"], "open_text")
    r = api.post(f"/api/admin/questions/{q['id']}/options", json={"label": "x"})
    assert r.status_code == 400


def test_cannot_delete_last_option(api):
    f = make_form(api)
    q = add_q(api, f["id"], "single_choice", options=["Ганц"])
    r = api.delete(f"/api/admin/options/{q['options'][0]['id']}")
    assert r.status_code == 400


# ============================ _lock_if_answered ============================
def test_answered_form_is_structurally_frozen(api, anon):
    fid, qs = published_form(api)
    single = qs["single"]
    assert submit(anon, fid, [{"question_id": single["id"],
                               "option_ids": [opt(single, 0)]}]).status_code == 201

    assert api.delete(f"/api/admin/questions/{single['id']}").status_code == 409
    assert api.delete(f"/api/admin/options/{opt(single, 1)}").status_code == 409
    assert api.post(f"/api/admin/questions/{single['id']}/options",
                    json={"label": "шинэ"}).status_code == 409
    assert api.put(f"/api/admin/questions/{single['id']}",
                   json={"question_type": "open_text"}).status_code == 409
    assert api.put(f"/api/admin/questions/{single['id']}",
                   json={"options": ["a"]}).status_code == 409
    # зөвшөөрөгдөх өөрчлөлтүүд
    assert api.put(f"/api/admin/options/{opt(single, 0)}",
                   json={"label": "Шинэ нэр"}).status_code == 200
    assert api.put(f"/api/admin/questions/{single['id']}",
                   json={"title": "Гарчиг сольсон"}).status_code == 200
    # бүтэц өөрчлөгдөөгүй
    q = api.get(f"/api/admin/questions/{single['id']}").get_json()
    assert len(q["options"]) == 3 and q["question_type"] == "single_choice"


# ============================ documents (PDF) ============================
def _upload(api, fid, files):
    data = {"file": [(io.BytesIO(b), n) for n, b in files]}
    return api.post(f"/api/admin/forms/{fid}/document", data=data,
                    content_type="multipart/form-data")


def test_document_upload_list_serve_delete(api, anon):
    f = make_form(api, type="poll")
    r = _upload(api, f["id"], [("хууль.pdf", PDF_BYTES), ("b.PDF", PDF_BYTES)])
    assert r.status_code == 201, r.get_json()
    docs = r.get_json()
    assert len(docs) == 2
    d = docs[0]
    assert d["file_name"] == "хууль.pdf" and d["mime_type"] == "application/pdf"
    assert d["file_size"] == len(PDF_BYTES) and d["url"].startswith("/uploads/form/")

    lst = api.get(f"/api/admin/forms/{f['id']}/documents")
    assert lst.status_code == 200 and len(lst.get_json()) == 2
    assert len(api.get(f"/api/admin/forms/{f['id']}").get_json()["documents"]) == 2
    assert api.get("/api/admin/forms/999999/documents").status_code == 404

    # токенгүй үйлчилнэ
    s = anon.get(d["url"])
    assert s.status_code == 200 and s.data == PDF_BYTES
    assert s.mimetype == "application/pdf"
    s.close()
    assert anon.get("/uploads/form/nope.pdf").status_code == 404

    r = api.delete(f"/api/admin/documents/{d['id']}")
    assert r.status_code == 200 and r.get_json()["deleted"] == d["id"]
    assert anon.get(d["url"]).status_code == 404          # диск дээрээс арилсан
    assert api.delete(f"/api/admin/documents/{d['id']}").status_code == 404


def test_document_upload_validation_is_atomic(api):
    f = make_form(api, type="poll")
    assert api.post(f"/api/admin/forms/{f['id']}/document", data={},
                    content_type="multipart/form-data").status_code == 400
    assert _upload(api, f["id"], [("a.txt", PDF_BYTES)]).status_code == 400
    assert _upload(api, f["id"], [("a.pdf", b"")]).status_code == 400
    assert _upload(api, f["id"], [("a.pdf", b"not a pdf at all")]).status_code == 400
    # нэг нь буруу бол юу ч хадгалагдахгүй
    assert _upload(api, f["id"], [("ok.pdf", PDF_BYTES),
                                  ("bad.pdf", b"garbage")]).status_code == 400
    assert api.get(f"/api/admin/forms/{f['id']}/documents").get_json() == []
    assert _upload(api, 999999, [("a.pdf", PDF_BYTES)]).status_code == 404


def test_hard_delete_form_removes_pdf(api, anon):
    f = make_form(api, type="poll")
    url = _upload(api, f["id"], [("a.pdf", PDF_BYTES)]).get_json()[0]["url"]
    assert api.delete(f"/api/admin/forms/{f['id']}").status_code == 200
    assert anon.get(url).status_code == 404


# ============================ portal: list / detail ============================
def test_portal_list_hides_drafts_and_deleted(api, anon):
    draft = make_form(api)
    add_q(api, draft["id"], "open_text")
    fid, _ = published_form(api)
    r = anon.get("/api/portal/forms")
    assert r.status_code == 200
    ids = [x["id"] for x in r.get_json()]
    assert fid in ids and draft["id"] not in ids
    item = next(x for x in r.get_json() if x["id"] == fid)
    assert item["total_questions"] == 4 and item["has_submitted"] is False

    assert fid in [x["id"] for x in anon.get("/api/portal/forms?active=1").get_json()]
    assert fid not in [x["id"] for x in anon.get("/api/portal/forms?type=poll").get_json()]
    assert fid not in [x["id"] for x in anon.get("/api/portal/forms?status=closed").get_json()]


def test_portal_list_active_excludes_expired_and_poll_documents(api, anon):
    f = make_form(api, type="poll", end_at="2020-01-01")
    add_q(api, f["id"], "open_text")
    api.post(f"/api/admin/forms/{f['id']}/publish")
    _upload(api, f["id"], [("a.pdf", PDF_BYTES)])
    lst = anon.get("/api/portal/forms?type=poll").get_json()
    item = next(x for x in lst if x["id"] == f["id"])
    assert item["is_open"] is False and len(item["documents"]) == 1
    assert f["id"] not in [x["id"] for x in anon.get("/api/portal/forms?active=1").get_json()]


def test_portal_detail(api, anon):
    draft = make_form(api)
    assert anon.get(f"/api/portal/forms/{draft['id']}").status_code == 404
    assert anon.get("/api/portal/forms/999999").status_code == 404
    fid, qs = published_form(api)
    r = anon.get(f"/api/portal/forms/{fid}")
    assert r.status_code == 200
    d = r.get_json()
    assert d["can_submit"] is True and d["has_submitted"] is False
    assert len(d["questions"]) == 4
