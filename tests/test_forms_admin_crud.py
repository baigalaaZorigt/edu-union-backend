"""Судалгаа / санал асуулгын engine — admin/forms.py + client/forms.py + core/forms_core.py — form CRUD, list / paging, questions."""

import pytest

from conftest import uniq

from _forms_helpers import add_q, make_form, opt, published_form, submit


# ============================ form CRUD ============================
def test_create_form_defaults(api):
    f = make_form(api, description="тайлбар")
    assert f["status"] == "draft"
    assert f["type"] == "survey"
    assert f["questions"] == [] and f["documents"] == []
    assert f["total_responses"] == 0
    assert f["is_open"] is False


def test_create_form_with_questions(api):
    r = api.post("/api/admin/forms", json={
        "title": uniq("F"), "type": "poll",
        "questions": [{"question_type": "single_choice", "title": "Q",
                       "options": [{"label": "Тийм"}, "Үгүй"]}]})
    assert r.status_code == 201
    q = r.get_json()["questions"][0]
    assert [o["label"] for o in q["options"]] == ["Тийм", "Үгүй"]


@pytest.mark.parametrize("body", [
    {},
    {"title": ""},
    {"title": "x", "type": "quiz"},
    {"title": "x", "start_at": "2026-13-01"},
    {"title": "x", "start_at": "2026-05-10", "end_at": "2026-05-01"},
])
def test_create_form_validation(api, body):
    assert api.post("/api/admin/forms", json=body).status_code == 400


def test_create_form_date_normalization(api):
    f = make_form(api, start_at="2026-01-01", end_at="2026-01-31T10:30")
    assert f["start_at"] == "2026-01-01 00:00:00"
    assert f["end_at"] == "2026-01-31 10:30:00"
    f2 = make_form(api, end_at="2026-02-01")
    assert f2["end_at"] == "2026-02-01 23:59:59"


def test_get_form_detail_and_404(api):
    f = make_form(api)
    r = api.get(f"/api/admin/forms/{f['id']}")
    assert r.status_code == 200 and r.get_json()["title"] == f["title"]
    assert api.get("/api/admin/forms/999999").status_code == 404


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_update_form(api, method):
    f = make_form(api)
    r = api.request(method, f"/api/admin/forms/{f['id']}",
                    json={"title": "Шинэ нэр", "show_results": False, "one_response": "0",
                          "type": "poll"})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["title"] == "Шинэ нэр" and d["type"] == "poll"
    assert d["show_results"] is False and d["one_response"] is False


def test_update_form_validation(api):
    f = make_form(api, start_at="2026-05-10")
    url = f"/api/admin/forms/{f['id']}"
    assert api.put(url, json={}).status_code == 400
    assert api.put(url, json={"status": "archived"}).status_code == 400
    assert api.put(url, json={"type": "x"}).status_code == 400
    # end_at < хадгалагдсан start_at
    assert api.put(url, json={"end_at": "2026-05-01"}).status_code == 400
    assert api.put("/api/admin/forms/999999", json={"title": "x"}).status_code == 404
    r = api.put(url, json={"status": "closed"})
    assert r.status_code == 200 and r.get_json()["status"] == "closed"


def test_publish_requires_questions_then_close(api):
    f = make_form(api)
    assert api.post(f"/api/admin/forms/{f['id']}/publish").status_code == 400
    add_q(api, f["id"], "open_text")
    r = api.post(f"/api/admin/forms/{f['id']}/publish")
    assert r.status_code == 200 and r.get_json()["status"] == "published"
    assert r.get_json()["is_open"] is True
    r = api.post(f"/api/admin/forms/{f['id']}/close")
    assert r.status_code == 200 and r.get_json()["status"] == "closed"
    assert api.post("/api/admin/forms/999999/publish").status_code == 404
    assert api.post("/api/admin/forms/999999/close").status_code == 404


def test_delete_form_without_answers_is_hard(api):
    f = make_form(api)
    add_q(api, f["id"])
    r = api.delete(f"/api/admin/forms/{f['id']}")
    assert r.status_code == 200 and r.get_json()["soft"] is False
    assert api.get(f"/api/admin/forms/{f['id']}").status_code == 404
    assert api.delete(f"/api/admin/forms/{f['id']}").status_code == 404


def test_delete_form_with_answers_soft_then_hard(api, anon):
    fid, qs = published_form(api)
    assert submit(anon, fid, [{"question_id": qs["single"]["id"],
                               "option_ids": [opt(qs["single"], 0)]}]).status_code == 201
    r = api.delete(f"/api/admin/forms/{fid}")
    assert r.status_code == 200 and r.get_json()["soft"] is True
    assert api.get(f"/api/admin/forms/{fid}").status_code == 404
    listed = api.get("/api/admin/forms?per_page=100").get_json()["items"]
    assert fid not in [x["id"] for x in listed]
    assert anon.get(f"/api/portal/forms/{fid}").status_code == 404

    fid2, qs2 = published_form(api)
    submit(anon, fid2, [{"question_id": qs2["single"]["id"],
                         "option_ids": [opt(qs2["single"], 0)]}])
    r = api.delete(f"/api/admin/forms/{fid2}?hard=1")
    assert r.status_code == 200 and r.get_json()["soft"] is False


# ============================ list / paging ============================
def test_list_forms_filters_and_paging(api):
    tag = uniq("ХАЙЛТ")
    ids = [make_form(api, title=f"{tag} {i}", type="poll")["id"] for i in range(3)]
    r = api.get(f"/api/admin/forms?search={tag}&per_page=2&page=1")
    assert r.status_code == 200
    d = r.get_json()
    assert d["total"] == 3 and d["pages"] == 2 and d["per_page"] == 2 and d["page"] == 1
    assert [x["id"] for x in d["items"]] == sorted(ids, reverse=True)[:2]
    d2 = api.get(f"/api/admin/forms?search={tag}&per_page=2&page=2").get_json()
    assert len(d2["items"]) == 1
    assert api.get(f"/api/admin/forms?search={tag}&type=survey").get_json()["total"] == 0
    assert api.get(f"/api/admin/forms?search={tag}&type=poll&status=draft").get_json()["total"] == 3
    item = d["items"][0]
    assert "total_questions" in item and "total_responses" in item


def test_list_forms_paging_validation(api):
    assert api.get("/api/admin/forms?page=abc").status_code == 400
    assert api.get("/api/admin/forms?per_page=x").status_code == 400
    assert api.get("/api/admin/forms?per_page=5000").get_json()["per_page"] == 100
    assert api.get("/api/admin/forms?per_page=0").get_json()["per_page"] == 1
    assert api.get("/api/admin/forms?page=-3").get_json()["page"] == 1


# ============================ questions ============================
def test_question_crud(api):
    f = make_form(api)
    q = add_q(api, f["id"], "single_choice", description="d", is_required=True)
    assert q["is_required"] is True and len(q["options"]) == 3

    r = api.get(f"/api/admin/questions/{q['id']}")
    assert r.status_code == 200 and r.get_json()["id"] == q["id"]
    assert api.get("/api/admin/questions/999999").status_code == 404

    lst = api.get(f"/api/admin/forms/{f['id']}/questions")
    assert lst.status_code == 200 and [x["id"] for x in lst.get_json()] == [q["id"]]
    assert api.get("/api/admin/forms/999999/questions").status_code == 404

    for method in ("PUT", "PATCH"):
        r = api.request(method, f"/api/admin/questions/{q['id']}",
                        json={"title": f"Засав {method}", "is_required": False})
        assert r.status_code == 200 and r.get_json()["title"] == f"Засав {method}"
        assert r.get_json()["is_required"] is False

    r = api.put(f"/api/admin/questions/{q['id']}", json={"options": ["X", "Y"]})
    assert [o["label"] for o in r.get_json()["options"]] == ["X", "Y"]

    r = api.delete(f"/api/admin/questions/{q['id']}")
    assert r.status_code == 200 and r.get_json()["deleted"] == q["id"]
    assert api.delete(f"/api/admin/questions/{q['id']}").status_code == 404


@pytest.mark.parametrize("body", [
    {"title": "x"},                                            # question_type алга
    {"question_type": "single_choice"},                        # title алга
    {"question_type": "essay", "title": "x"},
    {"question_type": "single_choice", "title": "x"},          # options алга
    {"question_type": "multiple_choice", "title": "x", "options": [{"label": " "}]},
    {"question_type": "scale", "title": "x", "settings": {"min": 5, "max": 3}},
    {"question_type": "scale", "title": "x", "settings": {"min": 0, "max": 5}},
    {"question_type": "scale", "title": "x", "settings": {"min": 1, "max": 11}},
    {"question_type": "scale", "title": "x", "settings": {"min": "1", "max": 5}},
    {"question_type": "open_text", "title": "x", "settings": [1, 2]},
    {"question_type": "open_text", "title": "   "},
])
def test_create_question_validation(api, body):
    f = make_form(api)
    assert api.post(f"/api/admin/forms/{f['id']}/questions", json=body).status_code == 400


def test_create_question_on_missing_form(api):
    r = api.post("/api/admin/forms/999999/questions",
                 json={"question_type": "open_text", "title": "x"})
    assert r.status_code == 404


def test_scale_settings_defaults_and_passthrough(api):
    f = make_form(api)
    q = add_q(api, f["id"], "scale")
    assert q["settings"] == {"min": 1, "max": 5}
    q2 = add_q(api, f["id"], "scale",
               settings={"min": 1, "max": 10, "min_label": "Муу", "max_label": "Сайн"})
    assert q2["settings"]["min_label"] == "Муу" and q2["settings"]["max"] == 10
    assert "options" not in q2


def test_update_question_validation(api):
    f = make_form(api)
    q = add_q(api, f["id"], "single_choice")
    url = f"/api/admin/questions/{q['id']}"
    assert api.put(url, json={}).status_code == 400
    assert api.put(url, json={"title": ""}).status_code == 400
    assert api.put(url, json={"question_type": "bad"}).status_code == 400
    assert api.put(url, json={"options": []}).status_code == 400
    assert api.put("/api/admin/questions/999999", json={"title": "x"}).status_code == 404


def test_change_question_type_to_text_drops_options(api):
    f = make_form(api)
    q = add_q(api, f["id"], "single_choice")
    r = api.put(f"/api/admin/questions/{q['id']}", json={"question_type": "open_text"})
    assert r.status_code == 200 and "options" not in r.get_json()
    r = api.put(f"/api/admin/questions/{q['id']}", json={"question_type": "scale"})
    assert r.status_code == 200 and r.get_json()["settings"] == {"min": 1, "max": 5}
    # scale -> choice болгоход сонголт автоматаар үүсэхгүй, options-ийг хамт өгнө
    r = api.put(f"/api/admin/questions/{q['id']}",
                json={"question_type": "multiple_choice", "options": ["a", "b"]})
    assert r.status_code == 200 and len(r.get_json()["options"]) == 2


def test_duplicate_question(api):
    f = make_form(api)
    q = add_q(api, f["id"], "multiple_choice", description="dd")
    r = api.post(f"/api/admin/questions/{q['id']}/duplicate")
    assert r.status_code == 201
    d = r.get_json()
    assert d["id"] != q["id"] and d["title"] == q["title"]
    assert d["sort_order"] > q["sort_order"]
    assert [o["label"] for o in d["options"]] == [o["label"] for o in q["options"]]
    assert {o["id"] for o in d["options"]}.isdisjoint({o["id"] for o in q["options"]})
    assert api.post("/api/admin/questions/999999/duplicate").status_code == 404


def test_reorder_questions(api):
    f = make_form(api)
    a = add_q(api, f["id"], "open_text")
    b = add_q(api, f["id"], "open_text")
    url = f"/api/admin/forms/{f['id']}/questions/reorder"
    r = api.post(url, json={"questions": [{"id": b["id"], "sort_order": 1},
                                          {"id": a["id"], "sort_order": 2}]})
    assert r.status_code == 200
    assert [x["id"] for x in r.get_json()] == [b["id"], a["id"]]
    # sort_order өгөөгүй бол жагсаалтын байрлал
    r = api.post(url, json={"questions": [{"id": a["id"]}, {"id": b["id"]}]})
    assert [x["id"] for x in r.get_json()] == [a["id"], b["id"]]

    assert api.post(url, json={}).status_code == 400
    assert api.post(url, json={"questions": []}).status_code == 400
    assert api.post(url, json={"questions": [{"sort_order": 1}]}).status_code == 400
    other = add_q(api, make_form(api)["id"], "open_text")
    assert api.post(url, json={"questions": [{"id": other["id"]}]}).status_code == 404
    assert api.post("/api/admin/forms/999999/questions/reorder",
                    json={"questions": [{"id": a["id"]}]}).status_code == 404
