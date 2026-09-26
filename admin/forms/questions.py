"""form_question (Асуулт барих) — CRUD, хуулбарлах, дараалал."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import require, json_body, insert_row, update_row
from core.forms_core import (
    CHOICE_TYPES, QUESTION_FIELDS, bad, now_str, insert_options, insert_question, next_sort,
    one_question, question_list, require_form, validate_question, _flag,
)

from admin.forms import bp
from admin.forms.common import _lock_if_answered, _question_or_404


# ====================== form_question (Асуулт барих) ======================
@bp.route("/api/admin/forms/<int:fid>/questions", methods=["GET"])
def list_questions(fid):
    conn = get_db()
    require_form(conn, fid)
    data = question_list(conn, fid)
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/forms/<int:fid>/questions", methods=["POST"])
def create_question(fid):
    """Асуулт нэмэх. Сонголттой төрөлд options: [{"label": "..."}] заавал."""
    data = request.get_json(silent=True)
    require(data, ["question_type", "title"])
    conn = get_db()
    require_form(conn, fid)
    qid = insert_question(conn, fid, data)
    conn.commit()
    out = one_question(conn, qid)
    conn.close()
    return jsonify(out), 201


@bp.route("/api/admin/questions/<int:qid>", methods=["GET"])
def get_question(qid):
    conn = get_db()
    out = one_question(conn, qid)
    conn.close()
    if not out:
        abort(404, description="Асуулт олдсонгүй")
    return jsonify(out)


@bp.route("/api/admin/questions/<int:qid>", methods=["PUT", "PATCH"])
def update_question(qid):
    """Асуулт засах. options өгвөл сонголтууд БҮРЭН солигдоно (хариултгүй үед л)."""
    data = json_body()
    conn = get_db()
    current = _question_or_404(conn, qid)
    qtype, settings = validate_question(conn, data, current)
    type_changed = qtype != current["question_type"]
    values = {}
    for f in QUESTION_FIELDS:
        if f not in data:
            continue
        val = data[f]
        if f == "question_type":
            val = qtype
        elif f == "settings":
            val = settings
        elif f == "is_required":
            val = _flag(val, 0)
        elif f == "title" and not str(val or "").strip():
            bad(conn, "title хоосон байж болохгүй")
        values[f] = val
    if type_changed:                            # төрөл солигдвол settings дагаж шинэчлэгдэнэ
        values.setdefault("settings", settings)

    replace = "options" in data
    if replace or type_changed:
        _lock_if_answered(conn, current["form_id"], "асуултын бүтцийг өөрчлөх")
    if not values and not replace:
        bad(conn, "Шинэчлэх талбар алга")
    if values:
        values["updated_at"] = now_str()
        update_row(conn, "form_question", qid, values)
    if replace:
        if qtype in CHOICE_TYPES and not data["options"]:
            bad(conn, f"{qtype} асуултад дор хаяж нэг options шаардлагатай")
        conn.execute("DELETE FROM form_option WHERE question_id=?", (qid,))
        insert_options(conn, qid, data["options"])
    elif qtype not in CHOICE_TYPES and type_changed:
        conn.execute("DELETE FROM form_option WHERE question_id=?", (qid,))
    conn.commit()
    out = one_question(conn, qid)
    conn.close()
    return jsonify(out)


@bp.route("/api/admin/questions/<int:qid>", methods=["DELETE"])
def delete_question(qid):
    conn = get_db()
    current = _question_or_404(conn, qid)
    _lock_if_answered(conn, current["form_id"], "асуулт устгах")
    conn.execute("DELETE FROM form_question WHERE id=?", (qid,))
    conn.commit()
    conn.close()
    return jsonify(deleted=qid)


@bp.route("/api/admin/questions/<int:qid>/duplicate", methods=["POST"])
def duplicate_question(qid):
    """Асуултыг сонголтуудтай нь хамт хуулж, төгсгөлд нь нэмнэ."""
    conn = get_db()
    src = _question_or_404(conn, qid)
    now = now_str()
    new_id = insert_row(conn, "form_question", {
        "form_id": src["form_id"], "question_type": src["question_type"],
        "title": src["title"], "description": src["description"],
        "is_required": src["is_required"],
        "sort_order": next_sort(conn, "form_question", "form_id", src["form_id"]),
        "settings": src["settings"], "created_at": now, "updated_at": now})
    conn.execute(
        "INSERT INTO form_option(question_id, label, sort_order, created_at) "
        "SELECT ?, label, sort_order, ? FROM form_option WHERE question_id=? "
        "ORDER BY sort_order, id", (new_id, now, qid))
    conn.commit()
    out = one_question(conn, new_id)
    conn.close()
    return jsonify(out), 201


@bp.route("/api/admin/forms/<int:fid>/questions/reorder", methods=["POST"])
def reorder_questions(fid):
    """Асуултын эрэмбийг хадгална: {"questions": [{"id": 10, "sort_order": 1}, ...]}"""
    data = json_body()
    items = data.get("questions")
    if not isinstance(items, list) or not items:
        abort(400, description="questions (жагсаалт) шаардлагатай")
    conn = get_db()
    require_form(conn, fid)
    updates = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            bad(conn, "questions доторх бичлэг бүр id-тай байна")
        qid = int(item["id"])
        if not conn.execute("SELECT 1 FROM form_question WHERE id=? AND form_id=?",
                            (qid, fid)).fetchone():
            bad(conn, f"Энэ маягтад харьяалагдахгүй асуулт: {qid}", 404)
        updates.append((item.get("sort_order") or i, now_str(), qid))
    conn.executemany(
        "UPDATE form_question SET sort_order=?, updated_at=? WHERE id=?", updates)
    conn.commit()
    data = question_list(conn, fid)
    conn.close()
    return jsonify(data)
