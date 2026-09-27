"""form_question (Асуулт барих) — CRUD, хуулбарлах, дараалал."""

from flask import jsonify, request, abort
from sqlalchemy import delete, select, update

from core.helpers import require, json_body
from core.orm import session
from core.orm.models import FormOption, FormQuestion
from core.forms_core import (
    CHOICE_TYPES, QUESTION_FIELDS, bad, now_str, insert_options, insert_question, next_sort,
    one_question, question_list, require_form, validate_question, _flag,
)

from admin.forms import bp
from admin.forms.common import _lock_if_answered, _question_or_404


# ====================== form_question (Асуулт барих) ======================
@bp.route("/api/admin/forms/<int:fid>/questions", methods=["GET"])
def list_questions(fid):
    require_form(fid)
    return jsonify(question_list(fid))


@bp.route("/api/admin/forms/<int:fid>/questions", methods=["POST"])
def create_question(fid):
    """Асуулт нэмэх. Сонголттой төрөлд options: [{"label": "..."}] заавал."""
    data = request.get_json(silent=True)
    require(data, ["question_type", "title"])
    require_form(fid)
    qid = insert_question(fid, data)
    session().commit()
    return jsonify(one_question(qid)), 201


@bp.route("/api/admin/questions/<int:qid>", methods=["GET"])
def get_question(qid):
    out = one_question(qid)
    if not out:
        abort(404, description="Асуулт олдсонгүй")
    return jsonify(out)


@bp.route("/api/admin/questions/<int:qid>", methods=["PUT", "PATCH"])
def update_question(qid):
    """Асуулт засах. options өгвөл сонголтууд БҮРЭН солигдоно (хариултгүй үед л)."""
    data = json_body()
    current = _question_or_404(qid)
    qtype, settings = validate_question(data, current)
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
            bad("title хоосон байж болохгүй")
        values[f] = val
    if type_changed:                            # төрөл солигдвол settings дагаж шинэчлэгдэнэ
        values.setdefault("settings", settings)

    replace = "options" in data
    if replace or type_changed:
        _lock_if_answered(current["form_id"], "асуултын бүтцийг өөрчлөх")
    if not values and not replace:
        bad("Шинэчлэх талбар алга")
    s = session()
    if values:
        values["updated_at"] = now_str()
        s.execute(update(FormQuestion).where(FormQuestion.id == qid).values(**values))
    if replace:
        if qtype in CHOICE_TYPES and not data["options"]:
            bad(f"{qtype} асуултад дор хаяж нэг options шаардлагатай")
        s.execute(delete(FormOption).where(FormOption.question_id == qid))
        insert_options(qid, data["options"])
    elif qtype not in CHOICE_TYPES and type_changed:
        s.execute(delete(FormOption).where(FormOption.question_id == qid))
    s.commit()
    return jsonify(one_question(qid))


@bp.route("/api/admin/questions/<int:qid>", methods=["DELETE"])
def delete_question(qid):
    current = _question_or_404(qid)
    _lock_if_answered(current["form_id"], "асуулт устгах")
    s = session()
    s.execute(delete(FormQuestion).where(FormQuestion.id == qid))
    s.commit()
    return jsonify(deleted=qid)


@bp.route("/api/admin/questions/<int:qid>/duplicate", methods=["POST"])
def duplicate_question(qid):
    """Асуултыг сонголтуудтай нь хамт хуулж, төгсгөлд нь нэмнэ."""
    src = _question_or_404(qid)
    now = now_str()
    s = session()
    copy = FormQuestion(
        form_id=src["form_id"], question_type=src["question_type"],
        title=src["title"], description=src["description"],
        is_required=src["is_required"],
        sort_order=next_sort(FormQuestion, FormQuestion.form_id, src["form_id"]),
        settings=src["settings"], created_at=now, updated_at=now)
    s.add(copy)
    s.flush()
    for o in s.scalars(select(FormOption).where(FormOption.question_id == qid)
                       .order_by(FormOption.sort_order, FormOption.id)).all():
        s.add(FormOption(question_id=copy.id, label=o.label, sort_order=o.sort_order,
                         created_at=now))
    s.commit()
    return jsonify(one_question(copy.id)), 201


@bp.route("/api/admin/forms/<int:fid>/questions/reorder", methods=["POST"])
def reorder_questions(fid):
    """Асуултын эрэмбийг хадгална: {"questions": [{"id": 10, "sort_order": 1}, ...]}"""
    data = json_body()
    items = data.get("questions")
    if not isinstance(items, list) or not items:
        abort(400, description="questions (жагсаалт) шаардлагатай")
    require_form(fid)
    s = session()
    updates = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            bad("questions доторх бичлэг бүр id-тай байна")
        qid = int(item["id"])
        if s.scalar(select(FormQuestion.id).where(FormQuestion.id == qid,
                                                  FormQuestion.form_id == fid)) is None:
            bad(f"Энэ маягтад харьяалагдахгүй асуулт: {qid}", 404)
        updates.append((qid, item.get("sort_order") or i, now_str()))
    for qid, order, ts in updates:
        s.execute(update(FormQuestion).where(FormQuestion.id == qid)
                  .values(sort_order=order, updated_at=ts))
    s.commit()
    return jsonify(question_list(fid))
