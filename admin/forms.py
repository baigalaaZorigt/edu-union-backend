"""Судалгаа / Санал асуулгын АДМИН тал (Blueprint).

Замын угтвар: /api/admin/... — маягт үүсгэх, асуулт барих, PDF хавсаргах, үр дүн харах.
Порталын тал (жагсаалт, бөглөх, илгээх) нь client/forms.py дотор.

Урсгал:
    Маягт үүсгэх -> Асуулт нэмэх -> Сонголт нэмэх -> Хугацаа тавих -> Нийтлэх (publish)
                 -> (хариултууд цуглана) -> Үр дүн харах -> Хаах (close)

Хариулт ирсэн маягтын БҮТЦИЙГ (асуулт/сонголт устгах, сонголт солих) өөрчлөхийг
хориглоно — өмнөх хариултууд утгаа алдахаас сэргийлнэ (409).
"""
import os
import uuid

from flask import Blueprint, jsonify, request, abort, g, send_from_directory

from db import get_db
from helpers import rows, require, json_body
from forms_core import (
    FORM_FIELDS, FORM_STATUSES, CHOICE_TYPES, QUESTION_FIELDS,
    MAX_PDF_SIZE, PDF_MAGIC, UPLOAD_DIR, UPLOAD_URL_PREFIX,
    bad, now_str, public_form, public_document, document_list,
    form_results, get_form, insert_options, insert_question,
    next_sort, one_question, open_text_answers, question_list, remove_upload,
    require_form, results_trend, submission_count, validate_form, validate_question,
    _flag,
)

bp = Blueprint("admin_forms", __name__)

MAX_PER_PAGE = 100


# ----------------------------- Туслахууд -----------------------------
def _user_id():
    """Одоо нэвтэрсэн хэрэглэгчийн id (created_by / updated_by-д бичнэ)."""
    user = getattr(g, "user", None)
    return user["id"] if user else None


def _lock_if_answered(conn, form_id, what):
    """Хариулт ирсэн бол бүтцийн өөрчлөлтийг зогсооно (409)."""
    if submission_count(conn, form_id):
        bad(conn, f"Энэ маягтад хариулт ирсэн тул {what} боломжгүй "
                  f"(шинэ маягт хуулбарлан үүсгэнэ үү)", 409)


def _question_or_404(conn, qid):
    row = conn.execute("SELECT * FROM form_question WHERE id=?", (qid,)).fetchone()
    if not row:
        bad(conn, "Асуулт олдсонгүй", 404)
    return row


def _detail(conn, row):
    """Маягтыг асуулт, PDF, хариултын тоотой нь хамт буцаана."""
    return public_form(row,
                       questions=question_list(conn, row["id"]),
                       documents=document_list(conn, row["id"]),
                       total_responses=submission_count(conn, row["id"]))


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
    row = require_form(conn, fid)
    data = _detail(conn, row)
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/forms", methods=["POST"])
def create_form():
    """Маягт үүсгэх. Заавал: title. Сонголтоор questions[] хамт илгээж болно."""
    data = request.get_json(silent=True)
    require(data, ["title"])
    conn = get_db()
    ftype, start, end = validate_form(conn, data)
    now = now_str()
    cur = conn.execute(
        "INSERT INTO form(type, title, description, status, start_at, end_at, "
        "show_results, one_response, created_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ftype, data["title"], data.get("description"), "draft", start, end,
         _flag(data.get("show_results")), _flag(data.get("one_response")),
         _user_id(), now, now))
    fid = cur.lastrowid
    for q in (data.get("questions") or []):     # маягтыг асуултуудтай нь нэг дор
        insert_question(conn, fid, q)
    conn.commit()
    row = get_form(conn, fid)
    out = _detail(conn, row)
    conn.close()
    return jsonify(out), 201


@bp.route("/api/admin/forms/<int:fid>", methods=["PUT"])
def update_form(fid):
    """Маягт засах (хэсэгчилсэн). status-г мөн энд эсвэл publish/close-оор солино."""
    data = json_body()
    conn = get_db()
    current = require_form(conn, fid)
    ftype, start, end = validate_form(conn, data, current)
    fields, values = [], []
    for f in FORM_FIELDS:
        if f not in data:
            continue
        val = data[f]
        if f == "type":
            val = ftype
        elif f == "start_at":
            val = start
        elif f == "end_at":
            val = end
        elif f in ("show_results", "one_response"):
            val = _flag(val)
        fields.append(f)
        values.append(val)
    if "status" in data:
        if data["status"] not in FORM_STATUSES:
            bad(conn, "status буруу. Сонголт: " + ", ".join(FORM_STATUSES))
        fields.append("status")
        values.append(data["status"])
    if not fields:
        bad(conn, "Шинэчлэх талбар алга")
    fields += ["updated_by", "updated_at"]
    values += [_user_id(), now_str(), fid]
    conn.execute(f"UPDATE form SET {', '.join(f + '=?' for f in fields)} WHERE id=?", values)
    conn.commit()
    out = _detail(conn, get_form(conn, fid))
    conn.close()
    return jsonify(out)


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
        conn.execute("UPDATE form SET deleted_at=?, updated_by=? WHERE id=?",
                     (now_str(), _user_id(), fid))
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
    conn = get_db()
    require_form(conn, fid)
    if not conn.execute("SELECT 1 FROM form_question WHERE form_id=?", (fid,)).fetchone():
        bad(conn, "Асуултгүй маягтыг нийтэлж болохгүй")
    conn.execute("UPDATE form SET status='published', updated_by=?, updated_at=? WHERE id=?",
                 (_user_id(), now_str(), fid))
    conn.commit()
    out = _detail(conn, get_form(conn, fid))
    conn.close()
    return jsonify(out)


@bp.route("/api/admin/forms/<int:fid>/close", methods=["POST"])
def close_form(fid):
    """Маягтыг хаах — шинэ хариулт хүлээж авахгүй (үр дүн хэвээр)."""
    conn = get_db()
    require_form(conn, fid)
    conn.execute("UPDATE form SET status='closed', updated_by=?, updated_at=? WHERE id=?",
                 (_user_id(), now_str(), fid))
    conn.commit()
    out = _detail(conn, get_form(conn, fid))
    conn.close()
    return jsonify(out)


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


@bp.route("/api/admin/questions/<int:qid>", methods=["PUT"])
def update_question(qid):
    """Асуулт засах. options өгвөл сонголтууд БҮРЭН солигдоно (хариултгүй үед л)."""
    data = json_body()
    conn = get_db()
    current = _question_or_404(conn, qid)
    qtype, settings = validate_question(conn, data, current)
    fields, values = [], []
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
        fields.append(f)
        values.append(val)
    if qtype != current["question_type"]:       # төрөл солигдвол settings дагаж шинэчлэгдэнэ
        if "settings" not in data:
            fields.append("settings")
            values.append(settings)

    replace = "options" in data
    if replace or qtype != current["question_type"]:
        _lock_if_answered(conn, current["form_id"], "асуултын бүтцийг өөрчлөх")
    if not fields and not replace:
        bad(conn, "Шинэчлэх талбар алга")
    if fields:
        fields.append("updated_at")
        values += [now_str(), qid]
        conn.execute(
            f"UPDATE form_question SET {', '.join(f + '=?' for f in fields)} WHERE id=?",
            values)
    if replace:
        if qtype in CHOICE_TYPES and not data["options"]:
            bad(conn, f"{qtype} асуултад дор хаяж нэг options шаардлагатай")
        conn.execute("DELETE FROM form_option WHERE question_id=?", (qid,))
        insert_options(conn, qid, data["options"])
    elif qtype not in CHOICE_TYPES and qtype != current["question_type"]:
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
    cur = conn.execute(
        "INSERT INTO form_question(form_id, question_type, title, description, "
        "is_required, sort_order, settings, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (src["form_id"], src["question_type"], src["title"], src["description"],
         src["is_required"], next_sort(conn, "form_question", "form_id", src["form_id"]),
         src["settings"], now, now))
    new_id = cur.lastrowid
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
    conn.execute(
        "INSERT INTO form_option(question_id, label, sort_order, created_at) VALUES (?,?,?,?)",
        (qid, data["label"], data.get("sort_order")
         or next_sort(conn, "form_option", "question_id", qid), now_str()))
    conn.commit()
    row = conn.execute("SELECT * FROM form_option WHERE question_id=? "
                       "ORDER BY id DESC LIMIT 1", (qid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/admin/options/<int:oid>", methods=["PUT"])
def update_option(oid):
    """Сонголтын нэр/эрэмбийг засна (хариултад нөлөөлөхгүй тул үргэлж боломжтой)."""
    data = json_body()
    conn = get_db()
    row = conn.execute("SELECT * FROM form_option WHERE id=?", (oid,)).fetchone()
    if not row:
        bad(conn, "Сонголт олдсонгүй", 404)
    fields, values = [], []
    for f in ("label", "sort_order"):
        if f in data:
            if f == "label" and not str(data[f] or "").strip():
                bad(conn, "label хоосон байж болохгүй")
            fields.append(f)
            values.append(data[f])
    if not fields:
        bad(conn, "Шинэчлэх талбар алга (label, sort_order)")
    fields.append("updated_at")
    values += [now_str(), oid]
    conn.execute(
        f"UPDATE form_option SET {', '.join(f + '=?' for f in fields)} WHERE id=?", values)
    conn.commit()
    out = dict(conn.execute("SELECT * FROM form_option WHERE id=?", (oid,)).fetchone())
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


# ====================== form_document (Санал асуулгын PDF) ======================
def _validate_pdf(f):
    """Нэг PDF-г шалгана: .pdf нэр, %PDF- толгой, ≤20 MB (буруу бол 400)."""
    name = (f.filename or "").strip()
    if not name:
        abort(400, description="Файлын нэр хоосон байна")
    if not name.lower().endswith(".pdf"):
        abort(400, description=f"'{name}': зөвхөн PDF файл оруулна")
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        abort(400, description=f"'{name}': файл хоосон байна")
    if size > MAX_PDF_SIZE:
        abort(400, description=(f"'{name}': файл 20 MB-аас хэтэрсэн байна "
                                f"({size / 1024 / 1024:.1f} MB)"))
    if f.stream.read(len(PDF_MAGIC)) != PDF_MAGIC:
        f.stream.seek(0)
        abort(400, description=f"'{name}': PDF файл биш байна")
    f.stream.seek(0)
    return name, size


@bp.route("/api/admin/forms/<int:fid>/documents", methods=["GET"])
def list_documents(fid):
    conn = get_db()
    require_form(conn, fid)
    data = document_list(conn, fid)
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/forms/<int:fid>/document", methods=["POST"])
def upload_document(fid):
    """Маягтад PDF хавсаргах — multipart/form-data, `file` талбар (олон байж болно).

    Бүх файлыг ЭХЛЭЭД шалгана — нэг нь буруу бол юу ч хадгалагдахгүй.
    """
    files = [f for f in request.files.getlist("file") + request.files.getlist("files") if f]
    if not files:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    checked = [_validate_pdf(f) for f in files]
    conn = get_db()
    require_form(conn, fid)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    now = now_str()
    new_ids = []
    for f, (name, size) in zip(files, checked):
        stored = f"{uuid.uuid4().hex}.pdf"
        f.save(os.path.join(UPLOAD_DIR, stored))
        cur = conn.execute(
            "INSERT INTO form_document(form_id, file_name, file_path, mime_type, "
            "file_size, created_at) VALUES (?,?,?,?,?,?)",
            (fid, name, UPLOAD_URL_PREFIX + stored, "application/pdf", size, now))
        new_ids.append(cur.lastrowid)
    conn.commit()
    ph = ", ".join("?" * len(new_ids))
    data = [public_document(r) for r in conn.execute(
        f"SELECT * FROM form_document WHERE id IN ({ph}) ORDER BY id", new_ids).fetchall()]
    conn.close()
    return jsonify(data), 201


@bp.route("/api/admin/documents/<int:did>", methods=["DELETE"])
def delete_document(did):
    conn = get_db()
    row = conn.execute("SELECT * FROM form_document WHERE id=?", (did,)).fetchone()
    if not row:
        bad(conn, "Файл олдсонгүй", 404)
    conn.execute("DELETE FROM form_document WHERE id=?", (did,))
    conn.commit()
    conn.close()
    remove_upload(row["file_path"])
    return jsonify(deleted=did)


@bp.route("/uploads/form/<path:stored_name>", methods=["GET"])
def serve_form_document(stored_name):
    """Хавсаргасан PDF-г үйлчилнэ — токен шаардахгүй (порталын PDF viewer).

    auth.py-ийн PUBLIC_PREFIXES ("/uploads/") энэ замыг нээлттэй болгодог.
    """
    path = os.path.join(UPLOAD_DIR, os.path.basename(stored_name))
    if not os.path.isfile(path):
        abort(404, description="Файл олдсонгүй")
    return send_from_directory(UPLOAD_DIR, os.path.basename(stored_name),
                               mimetype="application/pdf")


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
