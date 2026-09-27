"""form_option (Сонголт) — CRUD."""

from flask import jsonify, request
from sqlalchemy import delete, func, select, update

from core.helpers import require, json_body, pick
from core.orm import session
from core.orm.models import FormOption, FormQuestion
from core.forms_core import CHOICE_TYPES, bad, now_str, next_sort

from admin.forms import bp
from admin.forms.common import _lock_if_answered, _option_or_404, _question_or_404


# ====================== form_option (Сонголт) ======================
@bp.route("/api/admin/questions/<int:qid>/options", methods=["GET"])
def list_options(qid):
    _question_or_404(qid)
    return jsonify([o.to_dict() for o in session().scalars(
        select(FormOption).where(FormOption.question_id == qid)
        .order_by(FormOption.sort_order, FormOption.id))])


@bp.route("/api/admin/questions/<int:qid>/options", methods=["POST"])
def create_option(qid):
    """Ганц сонголт нэмэх: {"label": "...", "sort_order": 4}"""
    data = request.get_json(silent=True)
    require(data, ["label"])
    current = _question_or_404(qid)
    if current["question_type"] not in CHOICE_TYPES:
        bad(f"{current['question_type']} төрлийн асуултад сонголт байхгүй")
    _lock_if_answered(current["form_id"], "сонголт нэмэх")
    s = session()
    opt = FormOption(question_id=qid, label=data["label"],
                     sort_order=data.get("sort_order")
                     or next_sort(FormOption, FormOption.question_id, qid),
                     created_at=now_str())
    s.add(opt)
    s.commit()
    return jsonify(_option_or_404(opt.id)), 201


@bp.route("/api/admin/options/<int:oid>", methods=["PUT", "PATCH"])
def update_option(oid):
    """Сонголтын нэр/эрэмбийг засна (хариултад нөлөөлөхгүй тул үргэлж боломжтой)."""
    data = json_body()
    _option_or_404(oid)
    values = pick(data, ("label", "sort_order"))
    if "label" in values and not str(values["label"] or "").strip():
        bad("label хоосон байж болохгүй")
    if not values:
        bad("Шинэчлэх талбар алга (label, sort_order)")
    values["updated_at"] = now_str()
    s = session()
    s.execute(update(FormOption).where(FormOption.id == oid).values(**values))
    s.commit()
    return jsonify(_option_or_404(oid))


@bp.route("/api/admin/options/<int:oid>", methods=["DELETE"])
def delete_option(oid):
    s = session()
    row = s.execute(select(FormOption.question_id, FormQuestion.form_id)
                    .join(FormQuestion, FormQuestion.id == FormOption.question_id)
                    .where(FormOption.id == oid)).first()
    if row is None:
        bad("Сонголт олдсонгүй", 404)
    question_id, form_id = row
    _lock_if_answered(form_id, "сонголт устгах")
    if s.scalar(select(func.count()).select_from(FormOption)
                .where(FormOption.question_id == question_id)) <= 1:
        bad("Сүүлийн сонголтыг устгаж болохгүй — асуултаа бүхэлд нь устгана уу")
    s.execute(delete(FormOption).where(FormOption.id == oid))
    s.commit()
    return jsonify(deleted=oid)
