"""Маягтын админ маршрутуудын хуваалцсан туслахууд."""

from flask import jsonify
from sqlalchemy import select, update

from core.orm import session
from core.orm.models import Form, FormOption, FormQuestion
from core.forms_core import (
    bad, current_user_id, now_str, public_form, document_list, get_form, question_list,
    require_form, submission_count,
)


MAX_PER_PAGE = 100


# ----------------------------- Туслахууд -----------------------------
def _lock_if_answered(form_id, what):
    """Хариулт ирсэн бол бүтцийн өөрчлөлтийг зогсооно (409)."""
    if submission_count(form_id):
        bad(f"Энэ маягтад хариулт ирсэн тул {what} боломжгүй "
            f"(шинэ маягт хуулбарлан үүсгэнэ үү)", 409)


def _question_or_404(qid):
    obj = session().get(FormQuestion, qid)
    if obj is None:
        bad("Асуулт олдсонгүй", 404)
    return obj.to_dict()


def _option_or_404(oid):
    obj = session().get(FormOption, oid)
    if obj is None:
        bad("Сонголт олдсонгүй", 404)
    return obj.to_dict()


def _detail(row):
    """Маягтыг асуулт, PDF, хариултын тоотой нь хамт буцаана."""
    return public_form(row,
                       questions=question_list(row["id"]),
                       documents=document_list(row["id"]),
                       total_responses=submission_count(row["id"]))


def _detail_response(fid, status=200):
    """Маягтын дэлгэрэнгүйг уншиж JSON хариу буцаана."""
    return jsonify(_detail(get_form(fid))), status


def _set_status(fid, status):
    """Маягтын төлөвийг (published / closed) солиод дэлгэрэнгүйг буцаана."""
    require_form(fid)
    s = session()
    if status == "published" and s.scalar(
            select(FormQuestion.id).where(FormQuestion.form_id == fid).limit(1)) is None:
        bad("Асуултгүй маягтыг нийтэлж болохгүй")
    s.execute(update(Form).where(Form.id == fid).values(
        status=status, updated_by=current_user_id(), updated_at=now_str()))
    s.commit()
    return _detail_response(fid)
