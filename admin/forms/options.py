"""form_option (Сонголт) — CRUD."""

from flask import jsonify, request

from core.db import get_db
from core.helpers import rows, require, json_body, pick, insert_row, update_row
from core.forms_core import CHOICE_TYPES, bad, now_str, next_sort

from admin.forms import bp
from admin.forms.common import _lock_if_answered, _option_or_404, _question_or_404


# ====================== form_option (Сонголт) ======================
@bp.route("/api/admin/questions/<int:qid>/options", methods=["GET"])
def list_options(qid):
    conn = get_db()
    _question_or_404(conn, qid)
    data = rows(conn.execute(
        "SELECT * FROM form_option WHERE question_id=? ORDER BY sort_order, id",
        (qid,)).fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/questions/<int:qid>/options", methods=["POST"])
def create_option(qid):
    """Ганц сонголт нэмэх: {"label": "...", "sort_order": 4}"""
    data = request.get_json(silent=True)
    require(data, ["label"])
    conn = get_db()
    current = _question_or_404(conn, qid)
    if current["question_type"] not in CHOICE_TYPES:
        bad(conn, f"{current['question_type']} төрлийн асуултад сонголт байхгүй")
    _lock_if_answered(conn, current["form_id"], "сонголт нэмэх")
    oid = insert_row(conn, "form_option", {
        "question_id": qid, "label": data["label"],
        "sort_order": data.get("sort_order")
        or next_sort(conn, "form_option", "question_id", qid),
        "created_at": now_str()})
    conn.commit()
    row = _option_or_404(conn, oid)
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/admin/options/<int:oid>", methods=["PUT", "PATCH"])
def update_option(oid):
    """Сонголтын нэр/эрэмбийг засна (хариултад нөлөөлөхгүй тул үргэлж боломжтой)."""
    data = json_body()
    conn = get_db()
    _option_or_404(conn, oid)
    values = pick(data, ("label", "sort_order"))
    if "label" in values and not str(values["label"] or "").strip():
        bad(conn, "label хоосон байж болохгүй")
    if not values:
        bad(conn, "Шинэчлэх талбар алга (label, sort_order)")
    values["updated_at"] = now_str()
    update_row(conn, "form_option", oid, values)
    conn.commit()
    out = dict(_option_or_404(conn, oid))
    conn.close()
    return jsonify(out)


@bp.route("/api/admin/options/<int:oid>", methods=["DELETE"])
def delete_option(oid):
    conn = get_db()
    row = conn.execute(
        "SELECT o.*, q.form_id, q.question_type FROM form_option o "
        "JOIN form_question q ON q.id = o.question_id WHERE o.id=?", (oid,)).fetchone()
    if not row:
        bad(conn, "Сонголт олдсонгүй", 404)
    _lock_if_answered(conn, row["form_id"], "сонголт устгах")
    if conn.execute("SELECT COUNT(*) FROM form_option WHERE question_id=?",
                    (row["question_id"],)).fetchone()[0] <= 1:
        bad(conn, "Сүүлийн сонголтыг устгаж болохгүй — асуултаа бүхэлд нь устгана уу")
    conn.execute("DELETE FROM form_option WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    return jsonify(deleted=oid)
