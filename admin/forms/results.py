"""Үр дүн (form_result) — асуулт бүрээр, өдөр бүрээр, нээлттэй хариултууд."""

from flask import jsonify, request

from core.db import get_db
from core.forms_core import bad, form_results, open_text_answers, require_form, results_trend

from admin.forms import bp


# ====================== Үр дүн (form_result) ======================
@bp.route("/api/admin/forms/<int:fid>/results", methods=["GET"])
def get_results(fid):
    """Асуулт бүрийн нэгтгэсэн үр дүн — тоо, хувь, scale-ийн дундаж."""
    conn = get_db()
    require_form(conn, fid)
    data = form_results(conn, fid)
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/forms/<int:fid>/results/trend", methods=["GET"])
def get_results_trend(fid):
    """Өдөр бүрийн хариултын тоо (dashboard-ийн шугаман график)."""
    conn = get_db()
    require_form(conn, fid)
    data = results_trend(conn, fid)
    conn.close()
    return jsonify(items=data)


@bp.route("/api/admin/forms/<int:fid>/questions/<int:qid>/answers", methods=["GET"])
def get_question_answers(fid, qid):
    """Нээлттэй асуултын бичвэр хариултууд (?limit= &offset= хуудаслалттай)."""
    conn = get_db()
    require_form(conn, fid)
    row = conn.execute("SELECT * FROM form_question WHERE id=? AND form_id=?",
                       (qid, fid)).fetchone()
    if not row:
        bad(conn, "Энэ маягтад харьяалагдах асуулт олдсонгүй", 404)
    try:
        limit = int(request.args["limit"]) if request.args.get("limit") else None
        offset = int(request.args.get("offset", 0))
    except ValueError:
        bad(conn, "limit / offset нь тоо байх ёстой")
    data = open_text_answers(conn, qid, limit, offset)
    conn.close()
    return jsonify(question_id=qid, title=row["title"], answers=data)
