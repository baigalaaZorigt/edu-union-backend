"""Судалгаа / Санал асуулгын ПОРТАЛ тал (Blueprint).

Замын угтвар: /api/portal/... — НЭЭЛТТЭЙ (auth.py-ийн PUBLIC_PREFIXES): зочин
нэвтрэхгүйгээр идэвхтэй маягтуудыг хараад бөглөнө. Токен ирвэл бөглөлт тухайн
хэрэглэгчийн нэр дээр бүртгэгдэж, `one_response` дүрэм үйлчилнэ; зочны хувьд
хэн болохыг тогтоох боломжгүй тул давхардлыг хязгаарлахгүй (спекийн V1).
Админ тал (үүсгэх, асуулт барих, үр дүн) нь admin/forms.py дотор — тэнд токен + эрх шаардана.

Урсгал:
    Идэвхтэй маягтуудыг авах -> Судалгаа/санал асуулгыг нээх -> Асуултуудыг ачаалах
    -> Хариултаа бөглөх -> Илгээх (submit)

Илгээхэд спекийн 18-р хэсгийн шалгалтууд хийгдэнэ (маягт нийтлэгдсэн эсэх, хугацаа,
давхар бөглөлт [зөвхөн нэвтэрсэн үед], заавал асуулт, асуулт/сонголтын харьяалал,
төрлийн зөв эсэх).
Бүх шалгалт ЭХЛЭЭД хийгдэж, дараа нь илгээмж + хариултууд нэг гүйлгээгээр бичигдэнэ.
"""
from flask import Blueprint, jsonify, request, abort, g

from db import get_db
from helpers import json_body
from forms_core import (
    CHOICE_TYPES, bad, document_list, form_results, has_submitted, is_open,
    load_settings, now_str, public_form, question_list, require_form,
    submission_count,
)

bp = Blueprint("portal_forms", __name__)


def _uid():
    """Одоо нэвтэрсэн хэрэглэгчийн id, ЗОЧИН бол None.

    /api/portal/* нь нээлттэй (auth.py-ийн PUBLIC_PREFIXES) тул нэвтрээгүй хүн ч
    хандана — тэр үед g.user огт байхгүй. Токен ирсэн бол auth.py-ийн
    _optional_user() түүнийг аль хэдийн ачаалсан байна.
    """
    user = getattr(g, "user", None)
    return user["id"] if user else None


# ============================ Жагсаалт / дэлгэрэнгүй ============================
@bp.route("/api/portal/forms", methods=["GET"])
def list_forms():
    """Порталд харагдах маягтууд (ноорог болон устгагдсаныг ХАРУУЛАХГҮЙ).

    Шүүлт: ?type=survey|poll  ?status=published|closed  ?active=1 (одоо бөглөж болох)
    """
    conn = get_db()
    where, args = ["f.deleted_at IS NULL", "f.status <> 'draft'"], []
    if request.args.get("type"):
        where.append("f.type=?")
        args.append(request.args["type"])
    if request.args.get("status"):
        where.append("f.status=?")
        args.append(request.args["status"])
    data = conn.execute(
        "SELECT f.*, (SELECT COUNT(*) FROM form_question q WHERE q.form_id=f.id) "
        "AS total_questions, (SELECT COUNT(*) FROM form_submission s WHERE s.form_id=f.id "
        "AND s.user_id=?) AS mine FROM form f WHERE " + " AND ".join(where) +
        " ORDER BY f.id DESC", [_uid()] + args).fetchall()
    docs = {}
    for r in data:
        if r["type"] == "poll":
            docs[r["id"]] = document_list(conn, r["id"])
    conn.close()
    out = [public_form(r, total_questions=r["total_questions"],
                       has_submitted=bool(r["mine"]),
                       documents=docs.get(r["id"], [])) for r in data]
    if request.args.get("active") in ("1", "true", "True"):
        out = [f for f in out if f["is_open"]]
    return jsonify(out)


@bp.route("/api/portal/forms/<int:fid>", methods=["GET"])
def get_form_detail(fid):
    """Маягтын асуултууд, сонголтууд, хавсралт PDF + өөрөө бөглөсөн эсэх."""
    conn = get_db()
    row = require_form(conn, fid)
    if row["status"] == "draft":
        bad(conn, "Энэ маягт хараахан нийтлэгдээгүй байна", 404)
    mine = has_submitted(conn, fid, _uid())
    out = public_form(row,
                      questions=question_list(conn, fid),
                      documents=document_list(conn, fid),
                      has_submitted=mine,
                      can_submit=is_open(row) and not mine)
    conn.close()
    return jsonify(out)


@bp.route("/api/portal/forms/<int:fid>/results", methods=["GET"])
def get_public_results(fid):
    """Нийтэд нээлттэй үр дүн — show_results асаалттай үед л.

    Мөн өөрөө бөглөсөн эсвэл маягт хаагдсан үед л харагдана (санал нөлөөлөхөөс сэргийлнэ).
    """
    conn = get_db()
    row = require_form(conn, fid)
    if not row["show_results"]:
        bad(conn, "Энэ маягтын үр дүнг нийтэд харуулахгүй", 403)
    if row["status"] != "closed" and not has_submitted(conn, fid, _uid()):
        bad(conn, "Үр дүнг зөвхөн бөглөсний дараа харна", 403)
    data = form_results(conn, fid)
    conn.close()
    return jsonify(data)


# ============================ Бөглөх (submit) ============================
def _prepare_answer(conn, item, question, options):
    """Нэг хариултыг шалгаж (текст, тоо, сонголтууд) бэлдэнэ.

    Утга огт өгөөгүй бол None буцаана — тухайн асуултыг алгассан гэж үзнэ.
    """
    qtype = question["question_type"]
    title = question["title"]
    if qtype in CHOICE_TYPES:
        ids = item.get("option_ids")
        if ids in (None, [], ""):
            return None
        if not isinstance(ids, list):
            bad(conn, f"'{title}': option_ids нь жагсаалт байх ёстой")
        if qtype == "single_choice" and len(ids) != 1:
            bad(conn, f"'{title}': зөвхөн НЭГ сонголт хийнэ")
        chosen = []
        for oid in ids:
            if not str(oid).isdigit() or int(oid) not in options:
                bad(conn, f"'{title}': сонголт олдсонгүй эсвэл өөр асуултынх ({oid})")
            if int(oid) in chosen:
                bad(conn, f"'{title}': нэг сонголтыг давхардуулж илгээжээ ({oid})")
            chosen.append(int(oid))
        return {"option_ids": chosen}

    if qtype == "scale":
        value = item.get("numeric_value")
        if value in (None, ""):
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            bad(conn, f"'{title}': numeric_value нь бүхэл тоо байх ёстой")
        settings = load_settings(question["settings"]) or {}
        lo, hi = settings.get("min", 1), settings.get("max", 5)
        if value < lo or value > hi:
            bad(conn, f"'{title}': үнэлгээ {lo}-{hi} хооронд байна")
        return {"numeric_value": value}

    text = item.get("text_value")               # open_text
    if text in (None, ""):
        return None
    if not isinstance(text, str):
        bad(conn, f"'{title}': text_value нь текст байх ёстой")
    text = text.strip()
    return {"text_value": text} if text else None


@bp.route("/api/portal/forms/<int:fid>/submit", methods=["POST"])
def submit_form(fid):
    """Судалгаа / санал асуулгыг бөглөж илгээх.

    body: {"answers": [{"question_id": 1, "option_ids": [2]},
                       {"question_id": 3, "numeric_value": 4},
                       {"question_id": 4, "text_value": "..."}]}
    """
    data = json_body()
    answers = data.get("answers")
    if not isinstance(answers, list) or not answers:
        abort(400, description="answers (жагсаалт) шаардлагатай")

    conn = get_db()
    form = require_form(conn, fid)
    if form["status"] != "published":
        bad(conn, "Энэ маягт нийтлэгдээгүй эсвэл хаагдсан байна")
    now = now_str()
    if form["start_at"] and now < form["start_at"]:
        bad(conn, f"Бөглөх хугацаа {form['start_at']}-аас эхэлнэ")
    if form["end_at"] and now > form["end_at"]:
        bad(conn, f"Бөглөх хугацаа {form['end_at']}-д дууссан")
    uid = _uid()
    # one_response нь НЭВТЭРСЭН хэрэглэгчид л үйлчилнэ — зочны хувьд хэн болохыг
    # тогтоох боломжгүй (спекийн V1-д IP/төхөөрөмжийн хязгаарлалт шаардлагагүй).
    if form["one_response"] and uid and has_submitted(conn, fid, uid):
        bad(conn, "Та энэ маягтыг аль хэдийн бөглөсөн байна", 409)

    questions = {q["id"]: q for q in conn.execute(
        "SELECT * FROM form_question WHERE form_id=? ORDER BY sort_order, id",
        (fid,)).fetchall()}
    if not questions:
        bad(conn, "Энэ маягтад асуулт алга")
    options = {}
    for o in conn.execute(
            "SELECT o.id, o.question_id FROM form_option o "
            "JOIN form_question q ON q.id = o.question_id WHERE q.form_id=?",
            (fid,)).fetchall():
        options.setdefault(o["question_id"], set()).add(o["id"])

    # 1) Бүх хариултыг шалгаж бэлдэнэ (нэг нь ч буруу бол юу ч бичигдэхгүй)
    prepared = []
    for item in answers:
        if not isinstance(item, dict) or not str(item.get("question_id", "")).isdigit():
            bad(conn, "answers доторх бичлэг бүр question_id-тай байна")
        qid = int(item["question_id"])
        if qid not in questions:
            bad(conn, f"Энэ маягтад харьяалагдахгүй асуулт: {qid}")
        if any(p[0] == qid for p in prepared):
            bad(conn, f"Нэг асуултад хоёр хариулт илгээжээ: {qid}")
        value = _prepare_answer(conn, item, questions[qid], options.get(qid, set()))
        if value is not None:
            prepared.append((qid, value))

    # 2) Заавал хариулах асуултууд бүрэн эсэх
    answered = {qid for qid, _ in prepared}
    missing = [q["title"] for q in questions.values()
               if q["is_required"] and q["id"] not in answered]
    if missing:
        bad(conn, "Заавал хариулах асуулт дутуу: " + ", ".join(missing))
    if not prepared:
        bad(conn, "Хариулт хоосон байна")

    # 3) Илгээмж + хариултуудыг нэг гүйлгээгээр хадгална
    try:
        cur = conn.execute(
            "INSERT INTO form_submission(form_id, user_id, submitted_at, created_at) "
            "VALUES (?,?,?,?)", (fid, uid, now, now))
        sid = cur.lastrowid
        for qid, value in prepared:
            acur = conn.execute(
                "INSERT INTO form_answer(submission_id, question_id, text_value, "
                "numeric_value, created_at) VALUES (?,?,?,?,?)",
                (sid, qid, value.get("text_value"), value.get("numeric_value"), now))
            for oid in value.get("option_ids", []):
                conn.execute(
                    "INSERT INTO form_answer_option(answer_id, option_id) VALUES (?,?)",
                    (acur.lastrowid, oid))
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        abort(409, description="Хариулт хадгалахад алдаа гарлаа — дахин оролдоно уу")
    total = submission_count(conn, fid)
    conn.close()
    return jsonify(status=True, message="Таны санал бүртгэгдлээ.",
                   submission_id=sid, submitted_at=now, total_responses=total), 201
