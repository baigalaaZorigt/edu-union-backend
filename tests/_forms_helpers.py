"""Судалгаа / санал асуулгын engine — admin/forms.py + client/forms.py + core/forms_core.py — хуваалцсан туслахууд (test_forms_*.py ашиглана)."""

from conftest import uniq


# ----------------------------- туслахууд -----------------------------
def make_form(api, **extra):
    body = {"title": uniq("Судалгаа "), "type": "survey"}
    body.update(extra)
    r = api.post("/api/admin/forms", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def add_q(api, fid, qtype="single_choice", **extra):
    body = {"question_type": qtype, "title": uniq("Асуулт ")}
    if qtype in ("single_choice", "multiple_choice"):
        body["options"] = [{"label": "А"}, {"label": "Б"}, {"label": "В"}]
    body.update(extra)
    r = api.post(f"/api/admin/forms/{fid}/questions", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def published_form(api, **extra):
    """single + multiple + scale + open_text асуулттай нийтлэгдсэн маягт."""
    f = make_form(api, **extra)
    qs = {
        "single": add_q(api, f["id"], "single_choice", is_required=True),
        "multi": add_q(api, f["id"], "multiple_choice"),
        "scale": add_q(api, f["id"], "scale", settings={"min": 1, "max": 5}),
        "text": add_q(api, f["id"], "open_text"),
    }
    r = api.post(f"/api/admin/forms/{f['id']}/publish")
    assert r.status_code == 200, r.get_json()
    return f["id"], qs


def submit(client_api, fid, answers):
    return client_api.post(f"/api/portal/forms/{fid}/submit", json={"answers": answers})


def opt(q, i):
    return q["options"][i]["id"]
