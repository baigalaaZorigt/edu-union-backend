"""Судалгаа / санал асуулгын engine — admin/forms.py + client/forms.py + core/forms_core.py — portal: submit, portal: public results, auth."""

import pytest

from conftest import Api

from _forms_helpers import add_q, make_form, opt, published_form, submit


# ============================ portal: submit ============================
def test_guest_submit_not_deduplicated(api, anon):
    fid, qs = published_form(api, one_response=True)
    ans = [{"question_id": qs["single"]["id"], "option_ids": [opt(qs["single"], 0)]}]
    r1 = submit(anon, fid, ans)
    r2 = submit(anon, fid, ans)
    assert r1.status_code == 201 and r2.status_code == 201
    body = r2.get_json()
    assert body["status"] is True and body["total_responses"] == 2
    assert body["submission_id"] != r1.get_json()["submission_id"]


def test_logged_in_one_response(api, make_user):
    user_api, _ = make_user()
    fid, qs = published_form(api, one_response=True)
    ans = [{"question_id": qs["single"]["id"], "option_ids": [opt(qs["single"], 1)]}]
    assert submit(user_api, fid, ans).status_code == 201
    assert submit(user_api, fid, ans).status_code == 409
    d = user_api.get(f"/api/portal/forms/{fid}").get_json()
    assert d["has_submitted"] is True and d["can_submit"] is False
    item = next(x for x in user_api.get("/api/portal/forms").get_json() if x["id"] == fid)
    assert item["has_submitted"] is True

    fid2, qs2 = published_form(api, one_response=False)
    ans2 = [{"question_id": qs2["single"]["id"], "option_ids": [opt(qs2["single"], 0)]}]
    assert submit(user_api, fid2, ans2).status_code == 201
    assert submit(user_api, fid2, ans2).status_code == 201


def test_bad_token_on_portal_is_guest(api, client):
    fid, qs = published_form(api, one_response=True)
    bogus = Api(client, "not-a-jwt")
    ans = [{"question_id": qs["single"]["id"], "option_ids": [opt(qs["single"], 0)]}]
    assert submit(bogus, fid, ans).status_code == 201
    assert submit(bogus, fid, ans).status_code == 201


def test_submit_all_types_and_results(api, anon):
    fid, qs = published_form(api)
    s, m, sc, t = qs["single"], qs["multi"], qs["scale"], qs["text"]
    r = submit(anon, fid, [
        {"question_id": s["id"], "option_ids": [opt(s, 0)]},
        {"question_id": m["id"], "option_ids": [opt(m, 0), opt(m, 1)]},
        {"question_id": sc["id"], "numeric_value": 4},
        {"question_id": t["id"], "text_value": "  сайн  "},
    ])
    assert r.status_code == 201, r.get_json()
    r = submit(anon, fid, [
        {"question_id": s["id"], "option_ids": [str(opt(s, 1))]},
        {"question_id": m["id"], "option_ids": [opt(m, 0)]},
        {"question_id": sc["id"], "numeric_value": "2"},
    ])
    assert r.status_code == 201, r.get_json()

    res = api.get(f"/api/admin/forms/{fid}/results")
    assert res.status_code == 200
    d = res.get_json()
    assert d["form_id"] == fid and d["total_responses"] == 2
    by = {q["question_id"]: q for q in d["questions"]}

    single = by[s["id"]]
    assert single["total"] == 2
    assert [o["count"] for o in single["results"]] == [1, 1, 0]
    assert [o["percent"] for o in single["results"]] == [50.0, 50.0, 0]

    # multiple_choice: хувь нь асуулт тус бүрийн хариулагчаар — 100%-иас давж болно
    multi = by[m["id"]]
    assert multi["total"] == 2
    assert [o["percent"] for o in multi["results"]] == [100.0, 50.0, 0]
    assert sum(o["percent"] for o in multi["results"]) > 100

    # scale: 1..5 бүх утга, хариултгүйг 0-ээр бөглөнө
    scale = by[sc["id"]]
    assert scale["total"] == 2 and scale["average"] == 3.0
    assert scale["results"] == [{"value": v, "count": c}
                                for v, c in zip(range(1, 6), [0, 1, 0, 1, 0])]

    assert by[t["id"]]["total"] == 1
    assert "results" not in by[t["id"]]

    ans = api.get(f"/api/admin/forms/{fid}/questions/{t['id']}/answers")
    assert ans.status_code == 200
    a = ans.get_json()
    assert a["question_id"] == t["id"] and [x["text"] for x in a["answers"]] == ["сайн"]

    trend = api.get(f"/api/admin/forms/{fid}/results/trend")
    assert trend.status_code == 200
    items = trend.get_json()["items"]
    assert len(items) == 1 and items[0]["total"] == 2

    assert api.get(f"/api/admin/forms/{fid}").get_json()["total_responses"] == 2


def test_results_empty_form_and_404(api):
    f = make_form(api)
    q = add_q(api, f["id"], "scale", settings={"min": 3, "max": 6})
    d = api.get(f"/api/admin/forms/{f['id']}/results").get_json()
    assert d["total_responses"] == 0
    sq = d["questions"][0]
    assert sq["average"] is None and [x["value"] for x in sq["results"]] == [3, 4, 5, 6]
    assert api.get("/api/admin/forms/999999/results").status_code == 404
    assert api.get("/api/admin/forms/999999/results/trend").status_code == 404
    assert api.get(f"/api/admin/forms/{f['id']}/results/trend").get_json() == {"items": []}
    assert api.get(f"/api/admin/forms/{f['id']}/questions/999999/answers").status_code == 404
    other = make_form(api)
    assert api.get(f"/api/admin/forms/{other['id']}/questions/{q['id']}/answers").status_code == 404


def test_question_answers_paging(api, anon):
    fid, qs = published_form(api)
    s, t = qs["single"], qs["text"]
    for txt in ("нэг", "хоёр", "гурав"):
        submit(anon, fid, [{"question_id": s["id"], "option_ids": [opt(s, 0)]},
                           {"question_id": t["id"], "text_value": txt}])
    url = f"/api/admin/forms/{fid}/questions/{t['id']}/answers"
    assert len(api.get(url).get_json()["answers"]) == 3
    assert len(api.get(url + "?limit=2").get_json()["answers"]) == 2
    assert len(api.get(url + "?limit=2&offset=2").get_json()["answers"]) == 1
    assert api.get(url + "?limit=x").status_code == 400


@pytest.mark.parametrize("case", [
    "no_body", "empty_answers", "not_list", "no_qid", "foreign_q", "dup_q",
    "single_two", "option_not_list", "foreign_option", "dup_option",
    "scale_low", "scale_high", "scale_nan", "text_not_str", "missing_required",
])
def test_submit_validation(api, anon, case):
    fid, qs = published_form(api)
    s, m, sc, t = qs["single"], qs["multi"], qs["scale"], qs["text"]
    ok = {"question_id": s["id"], "option_ids": [opt(s, 0)]}
    other_fid, other_qs = published_form(api)
    bodies = {
        "empty_answers": {"answers": []},
        "not_list": {"answers": {"a": 1}},
        "no_qid": {"answers": [ok, {"text_value": "x"}]},
        "foreign_q": {"answers": [ok, {"question_id": other_qs["text"]["id"], "text_value": "x"}]},
        "dup_q": {"answers": [ok, ok]},
        "single_two": {"answers": [{"question_id": s["id"], "option_ids": [opt(s, 0), opt(s, 1)]}]},
        "option_not_list": {"answers": [ok, {"question_id": m["id"], "option_ids": opt(m, 0)}]},
        "foreign_option": {"answers": [{"question_id": s["id"], "option_ids": [opt(m, 0)]}]},
        "dup_option": {"answers": [ok, {"question_id": m["id"], "option_ids": [opt(m, 0), opt(m, 0)]}]},
        "scale_low": {"answers": [ok, {"question_id": sc["id"], "numeric_value": 0}]},
        "scale_high": {"answers": [ok, {"question_id": sc["id"], "numeric_value": 6}]},
        "scale_nan": {"answers": [ok, {"question_id": sc["id"], "numeric_value": "abc"}]},
        "text_not_str": {"answers": [ok, {"question_id": t["id"], "text_value": 5}]},
        "missing_required": {"answers": [{"question_id": t["id"], "text_value": "x"}]},
    }
    if case == "no_body":
        r = anon.post(f"/api/portal/forms/{fid}/submit", data="nope",
                      content_type="text/plain")
    else:
        r = anon.post(f"/api/portal/forms/{fid}/submit", json=bodies[case])
    assert r.status_code == 400, (case, r.get_json())
    # юу ч бичигдээгүй
    assert api.get(f"/api/admin/forms/{fid}").get_json()["total_responses"] == 0


def test_submit_skipped_answers_only_is_rejected(api, anon):
    f = make_form(api)
    q = add_q(api, f["id"], "open_text")
    api.post(f"/api/admin/forms/{f['id']}/publish")
    r = submit(anon, f["id"], [{"question_id": q["id"], "text_value": "   "}])
    assert r.status_code == 400


def test_submit_draft_closed_expired_future(api, anon):
    draft = make_form(api)
    q = add_q(api, draft["id"], "open_text")
    ans = [{"question_id": q["id"], "text_value": "x"}]
    assert submit(anon, draft["id"], ans).status_code == 400
    assert submit(anon, 999999, ans).status_code == 404

    api.post(f"/api/admin/forms/{draft['id']}/publish")
    assert submit(anon, draft["id"], ans).status_code == 201
    api.post(f"/api/admin/forms/{draft['id']}/close")
    assert submit(anon, draft["id"], ans).status_code == 400

    for dates in ({"end_at": "2020-01-01"}, {"start_at": "2099-01-01"}):
        f = make_form(api, **dates)
        qq = add_q(api, f["id"], "open_text")
        api.post(f"/api/admin/forms/{f['id']}/publish")
        assert submit(anon, f["id"], [{"question_id": qq["id"],
                                       "text_value": "x"}]).status_code == 400
        assert anon.get(f"/api/portal/forms/{f['id']}").get_json()["can_submit"] is False


def test_scale_custom_range_submit(api, anon):
    f = make_form(api)
    q = add_q(api, f["id"], "scale", settings={"min": 1, "max": 10})
    api.post(f"/api/admin/forms/{f['id']}/publish")
    assert submit(anon, f["id"], [{"question_id": q["id"], "numeric_value": 10}]).status_code == 201
    assert submit(anon, f["id"], [{"question_id": q["id"], "numeric_value": 11}]).status_code == 400


# ============================ portal: public results ============================
def test_public_results_rules(api, anon, make_user):
    fid, qs = published_form(api, show_results=True)
    ans = [{"question_id": qs["single"]["id"], "option_ids": [opt(qs["single"], 0)]}]
    # бөглөөгүй, хаагдаагүй -> 403
    assert anon.get(f"/api/portal/forms/{fid}/results").status_code == 403
    user_api, _ = make_user()
    assert submit(user_api, fid, ans).status_code == 201
    r = user_api.get(f"/api/portal/forms/{fid}/results")
    assert r.status_code == 200 and r.get_json()["total_responses"] == 1
    # зочин бөглөсөн ч танигдахгүй
    submit(anon, fid, ans)
    assert anon.get(f"/api/portal/forms/{fid}/results").status_code == 403
    api.post(f"/api/admin/forms/{fid}/close")
    assert anon.get(f"/api/portal/forms/{fid}/results").status_code == 200

    hidden, _ = published_form(api, show_results=False)
    api.post(f"/api/admin/forms/{hidden}/close")
    assert anon.get(f"/api/portal/forms/{hidden}/results").status_code == 403
    assert anon.get("/api/portal/forms/999999/results").status_code == 404


# ============================ auth ============================
def test_admin_forms_require_token_and_permission(anon, make_user):
    assert anon.get("/api/admin/forms").status_code == 401
    assert anon.post("/api/admin/forms", json={"title": "x"}).status_code == 401
    user_api, _ = make_user()
    assert user_api.get("/api/admin/forms").status_code == 403
    assert user_api.post("/api/admin/forms", json={"title": "x"}).status_code == 403


def test_wrong_method_is_json_405(api):
    r = api.delete("/api/admin/forms")
    assert r.status_code == 405 and "error" in r.get_json()
