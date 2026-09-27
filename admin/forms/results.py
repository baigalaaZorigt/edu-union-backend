"""Үр дүн (form_result) — асуулт бүрээр, өдөр бүрээр, нээлттэй хариултууд."""

from flask import jsonify, request

from core.orm import session
from core.orm.models import FormQuestion
from core.forms_core import bad, form_results, open_text_answers, require_form, results_trend

from admin.forms import bp


# ====================== Үр дүн (form_result) ======================
@bp.route("/api/admin/forms/<int:fid>/results", methods=["GET"])
def get_results(fid):
    """Асуулт бүрийн нэгтгэсэн үр дүн — тоо, хувь, scale-ийн дундаж."""
    require_form(fid)
    return jsonify(form_results(fid))


@bp.route("/api/admin/forms/<int:fid>/results/trend", methods=["GET"])
def get_results_trend(fid):
    """Өдөр бүрийн хариултын тоо (dashboard-ийн шугаман график)."""
    require_form(fid)
    return jsonify(items=results_trend(fid))


@bp.route("/api/admin/forms/<int:fid>/questions/<int:qid>/answers", methods=["GET"])
def get_question_answers(fid, qid):
    """Нээлттэй асуултын бичвэр хариултууд (?limit= &offset= хуудаслалттай)."""
    require_form(fid)
    row = session().get(FormQuestion, qid)
    if row is None or row.form_id != fid:
        bad("Энэ маягтад харьяалагдах асуулт олдсонгүй", 404)
    try:
        limit = int(request.args["limit"]) if request.args.get("limit") else None
        offset = int(request.args.get("offset", 0))
    except ValueError:
        bad("limit / offset нь тоо байх ёстой")
    data = open_text_answers(qid, limit, offset)
    return jsonify(question_id=qid, title=row.title, answers=data)
