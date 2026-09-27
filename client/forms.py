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
from flask import Blueprint, jsonify, request, abort
from sqlalchemy import func, select

from core.helpers import json_body, list_json, slice_page
from core.orm import session
from core.orm.models import (
    Form, FormAnswer, FormAnswerOption, FormOption, FormQuestion, FormSubmission,
)
from core.forms_core import (
    CHOICE_TYPES, bad, current_user_id, document_list, form_results, has_submitted,
    is_open, load_settings, now_str, public_form, question_list, question_rows, require_form,
    scale_range, submission_count,
)

bp = Blueprint("portal_forms", __name__)


# ============================ Жагсаалт / дэлгэрэнгүй ============================
@bp.route("/api/portal/forms", methods=["GET"])
def list_forms():
    """Порталд харагдах маягтууд (ноорог болон устгагдсаныг ХАРУУЛАХГҮЙ).

    Шүүлт: ?type=survey|poll  ?status=published|closed  ?active=1 (одоо бөглөж болох)
    """
    conds = [Form.deleted_at.is_(None), Form.status != "draft"]
    if request.args.get("type"):
        conds.append(Form.type == request.args["type"])
    if request.args.get("status"):
        conds.append(Form.status == request.args["status"])
    questions = (select(func.count()).select_from(FormQuestion)
                 .where(FormQuestion.form_id == Form.id).scalar_subquery())
    mine = (select(func.count()).select_from(FormSubmission)
            .where(FormSubmission.form_id == Form.id,
                   FormSubmission.user_id == current_user_id()).scalar_subquery())
    data = [(f.to_dict(), tq, m) for f, tq, m in session().execute(
        select(Form, questions, mine).where(*conds).order_by(Form.id.desc())).all()]
    docs = {r["id"]: document_list(r["id"]) for r, _, _ in data if r["type"] == "poll"}
    out = [public_form(r, total_questions=tq, has_submitted=bool(m),
                       documents=docs.get(r["id"], [])) for r, tq, m in data]
    if request.args.get("active") in ("1", "true", "True"):
        out = [f for f in out if f["is_open"]]
    return list_json(*slice_page(out))


@bp.route("/api/portal/forms/<int:fid>", methods=["GET"])
def get_form_detail(fid):
    """Маягтын асуултууд, сонголтууд, хавсралт PDF + өөрөө бөглөсөн эсэх."""
    row = require_form(fid)
    if row["status"] == "draft":
        bad("Энэ маягт хараахан нийтлэгдээгүй байна", 404)
    mine = has_submitted(fid, current_user_id())
    return jsonify(public_form(row,
                               questions=question_list(fid),
                               documents=document_list(fid),
                               has_submitted=mine,
                               can_submit=is_open(row) and not mine))


@bp.route("/api/portal/forms/<int:fid>/results", methods=["GET"])
def get_public_results(fid):
    """Нийтэд нээлттэй үр дүн — show_results асаалттай үед л.

    Мөн өөрөө бөглөсөн эсвэл маягт хаагдсан үед л харагдана (санал нөлөөлөхөөс сэргийлнэ).
    """
    row = require_form(fid)
    if not row["show_results"]:
        bad("Энэ маягтын үр дүнг нийтэд харуулахгүй", 403)
    if row["status"] != "closed" and not has_submitted(fid, current_user_id()):
        bad("Үр дүнг зөвхөн бөглөсний дараа харна", 403)
    return jsonify(form_results(fid))


# ============================ Бөглөх (submit) ============================
def _prepare_answer(item, question, options):
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
            bad(f"'{title}': option_ids нь жагсаалт байх ёстой")
        if qtype == "single_choice" and len(ids) != 1:
            bad(f"'{title}': зөвхөн НЭГ сонголт хийнэ")
        chosen = []
        for oid in ids:
            if not str(oid).isdigit() or int(oid) not in options:
                bad(f"'{title}': сонголт олдсонгүй эсвэл өөр асуултынх ({oid})")
            if int(oid) in chosen:
                bad(f"'{title}': нэг сонголтыг давхардуулж илгээжээ ({oid})")
            chosen.append(int(oid))
        return {"option_ids": chosen}

    if qtype == "scale":
        value = item.get("numeric_value")
        if value in (None, ""):
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            bad(f"'{title}': numeric_value нь бүхэл тоо байх ёстой")
        lo, hi = scale_range(load_settings(question["settings"]))
        if value < lo or value > hi:
            bad(f"'{title}': үнэлгээ {lo}-{hi} хооронд байна")
        return {"numeric_value": value}

    text = item.get("text_value")               # open_text
    if text in (None, ""):
        return None
    if not isinstance(text, str):
        bad(f"'{title}': text_value нь текст байх ёстой")
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

    form = require_form(fid)
    if form["status"] != "published":
        bad("Энэ маягт нийтлэгдээгүй эсвэл хаагдсан байна")
    now = now_str()
    if form["start_at"] and now < form["start_at"]:
        bad(f"Бөглөх хугацаа {form['start_at']}-аас эхэлнэ")
    if form["end_at"] and now > form["end_at"]:
        bad(f"Бөглөх хугацаа {form['end_at']}-д дууссан")
    uid = current_user_id()
    # one_response нь НЭВТЭРСЭН хэрэглэгчид л үйлчилнэ — зочны хувьд хэн болохыг
    # тогтоох боломжгүй (спекийн V1-д IP/төхөөрөмжийн хязгаарлалт шаардлагагүй).
    if form["one_response"] and uid and has_submitted(fid, uid):
        bad("Та энэ маягтыг аль хэдийн бөглөсөн байна", 409)

    questions = {q["id"]: q for q in question_rows(fid)}
    if not questions:
        bad("Энэ маягтад асуулт алга")
    options = {}
    s = session()
    for oid, question_id in s.execute(
            select(FormOption.id, FormOption.question_id)
            .join(FormQuestion, FormQuestion.id == FormOption.question_id)
            .where(FormQuestion.form_id == fid)):
        options.setdefault(question_id, set()).add(oid)

    # 1) Бүх хариултыг шалгаж бэлдэнэ (нэг нь ч буруу бол юу ч бичигдэхгүй)
    prepared, seen = [], set()
    for item in answers:
        if not isinstance(item, dict) or not str(item.get("question_id", "")).isdigit():
            bad("answers доторх бичлэг бүр question_id-тай байна")
        qid = int(item["question_id"])
        if qid not in questions:
            bad(f"Энэ маягтад харьяалагдахгүй асуулт: {qid}")
        if qid in seen:
            bad(f"Нэг асуултад хоёр хариулт илгээжээ: {qid}")
        value = _prepare_answer(item, questions[qid], options.get(qid, set()))
        if value is not None:               # алгассан (хоосон) хариулт давхардалд тооцогдохгүй
            seen.add(qid)
            prepared.append((qid, value))

    # 2) Заавал хариулах асуултууд бүрэн эсэх
    missing = [q["title"] for q in questions.values()
               if q["is_required"] and q["id"] not in seen]
    if missing:
        bad("Заавал хариулах асуулт дутуу: " + ", ".join(missing))
    if not prepared:
        bad("Хариулт хоосон байна")

    # 3) Илгээмж + хариултуудыг нэг гүйлгээгээр хадгална
    try:
        sub = FormSubmission(form_id=fid, user_id=uid, submitted_at=now, created_at=now)
        s.add(sub)
        s.flush()
        sid = sub.id
        for qid, value in prepared:
            ans = FormAnswer(submission_id=sid, question_id=qid,
                             text_value=value.get("text_value"),
                             numeric_value=value.get("numeric_value"), created_at=now)
            s.add(ans)
            s.flush()
            for oid in value.get("option_ids", []):
                s.add(FormAnswerOption(answer_id=ans.id, option_id=oid))
        s.commit()
    except Exception:
        s.rollback()
        abort(409, description="Хариулт хадгалахад алдаа гарлаа — дахин оролдоно уу")
    total = submission_count(fid)
    return jsonify(status=True, message="Таны санал бүртгэгдлээ.",
                   submission_id=sid, submitted_at=now, total_responses=total), 201
