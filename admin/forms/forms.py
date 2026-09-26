"""form (Маягт) — жагсаалт, үүсгэх, засах, устгах, нийтлэх, хаах."""

from flask import jsonify, request

from core.db import get_db
from core.helpers import require, json_body, insert_row, update_row
from core.forms_core import (
    FORM_FIELDS, FORM_STATUSES, bad, current_user_id, now_str, public_form, insert_question,
    remove_upload, require_form, submission_count, validate_form, _flag,
)

from admin.forms import bp
from admin.forms.common import MAX_PER_PAGE, _detail_response, _set_status


# ============================ form (Маягт) ============================
@bp.route("/api/admin/forms", methods=["GET"])
def list_forms():
    """Маягтын жагсаалт. Шүүлт: ?type= &status= &search= &page= &per_page=

    Буцаалт: {items, total, page, per_page, pages}
    """
    conn = get_db()
    where, args = ["f.deleted_at IS NULL"], []
    if request.args.get("type"):
        where.append("f.type=?")
        args.append(request.args["type"])
    if request.args.get("status"):
        where.append("f.status=?")
        args.append(request.args["status"])
    search = (request.args.get("search") or "").strip()
    if search:
        where.append("(f.title LIKE ? OR f.description LIKE ?)")
        args += [f"%{search}%", f"%{search}%"]
    clause = " WHERE " + " AND ".join(where)

    total = conn.execute("SELECT COUNT(*) FROM form f" + clause, args).fetchone()[0]
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        bad(conn, "page / per_page нь тоо байх ёстой")
    data = conn.execute(
        "SELECT f.*, (SELECT COUNT(*) FROM form_submission s WHERE s.form_id=f.id) "
        "AS total_responses, (SELECT COUNT(*) FROM form_question q WHERE q.form_id=f.id) "
        "AS total_questions FROM form f" + clause +
        " ORDER BY f.id DESC LIMIT ? OFFSET ?",
        args + [per_page, (page - 1) * per_page]).fetchall()
    conn.close()
    items = [public_form(r, total_responses=r["total_responses"],
                         total_questions=r["total_questions"]) for r in data]
    return jsonify(items=items, total=total, page=page, per_page=per_page,
                   pages=(total + per_page - 1) // per_page)


@bp.route("/api/admin/forms/<int:fid>", methods=["GET"])
def get_form_detail(fid):
    """Маягт + асуултууд + сонголтууд + хавсаргасан PDF."""
    conn = get_db()
    require_form(conn, fid)
    return _detail_response(conn, fid)


@bp.route("/api/admin/forms", methods=["POST"])
def create_form():
    """Маягт үүсгэх. Заавал: title. Сонголтоор questions[] хамт илгээж болно."""
    data = request.get_json(silent=True)
    require(data, ["title"])
    conn = get_db()
    ftype, start, end = validate_form(conn, data)
    now = now_str()
    fid = insert_row(conn, "form", {
        "type": ftype, "title": data["title"], "description": data.get("description"),
        "status": "draft", "start_at": start, "end_at": end,
        "show_results": _flag(data.get("show_results")),
        "one_response": _flag(data.get("one_response")),
        "created_by": current_user_id(), "created_at": now, "updated_at": now})
    for q in (data.get("questions") or []):     # маягтыг асуултуудтай нь нэг дор
        insert_question(conn, fid, q)
    conn.commit()
    return _detail_response(conn, fid, 201)


@bp.route("/api/admin/forms/<int:fid>", methods=["PUT", "PATCH"])
def update_form(fid):
    """Маягт засах (хэсэгчилсэн). status-г мөн энд эсвэл publish/close-оор солино."""
    data = json_body()
    conn = get_db()
    current = require_form(conn, fid)
    ftype, start, end = validate_form(conn, data, current)
    normalized = {"type": ftype, "start_at": start, "end_at": end}
    values = {}
    for f in FORM_FIELDS:
        if f not in data:
            continue
        if f in normalized:
            values[f] = normalized[f]
        elif f in ("show_results", "one_response"):
            values[f] = _flag(data[f])
        else:
            values[f] = data[f]
    if "status" in data:
        if data["status"] not in FORM_STATUSES:
            bad(conn, "status буруу. Сонголт: " + ", ".join(FORM_STATUSES))
        values["status"] = data["status"]
    if not values:
        bad(conn, "Шинэчлэх талбар алга")
    values.update(updated_by=current_user_id(), updated_at=now_str())
    update_row(conn, "form", fid, values)
    conn.commit()
    return _detail_response(conn, fid)


@bp.route("/api/admin/forms/<int:fid>", methods=["DELETE"])
def delete_form(fid):
    """Маягт устгах.

    Хариулт ИРЭЭГҮЙ бол бүрмөсөн устгана (асуулт/сонголт/PDF нь cascade-аар).
    Хариулт ИРСЭН бол зөөлөн устгал — deleted_at тавьж архивлана (үр дүн хадгалагдана).
    ?hard=1 өгвөл хариулттай ч гэсэн бүрмөсөн устгана.
    """
    conn = get_db()
    require_form(conn, fid)
    hard = request.args.get("hard") in ("1", "true", "True")
    if not hard and submission_count(conn, fid):
        update_row(conn, "form", fid, {"deleted_at": now_str(),
                                       "updated_by": current_user_id()})
        conn.commit()
        conn.close()
        return jsonify(deleted=fid, soft=True,
                       message="Хариулттай тул архивлав (устгасан төлөвт шилжив)")
    paths = [r["file_path"] for r in conn.execute(
        "SELECT file_path FROM form_document WHERE form_id=?", (fid,)).fetchall()]
    conn.execute("DELETE FROM form WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    for p in paths:
        remove_upload(p)
    return jsonify(deleted=fid, soft=False)


@bp.route("/api/admin/forms/<int:fid>/publish", methods=["POST"])
def publish_form(fid):
    """Маягтыг нийтлэх — порталд харагдаж, бөглөх боломжтой болно."""
    return _set_status(fid, "published")


@bp.route("/api/admin/forms/<int:fid>/close", methods=["POST"])
def close_form(fid):
    """Маягтыг хаах — шинэ хариулт хүлээж авахгүй (үр дүн хэвээр)."""
    return _set_status(fid, "closed")
