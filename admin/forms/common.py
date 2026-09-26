"""Маягтын админ маршрутуудын хуваалцсан туслахууд."""

from flask import jsonify

from core.db import get_db
from core.helpers import update_row
from core.forms_core import (
    bad, current_user_id, now_str, public_form, document_list, get_form, question_list,
    require_form, submission_count,
)


MAX_PER_PAGE = 100


# ----------------------------- Туслахууд -----------------------------
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


def _option_or_404(conn, oid):
    row = conn.execute("SELECT * FROM form_option WHERE id=?", (oid,)).fetchone()
    if not row:
        bad(conn, "Сонголт олдсонгүй", 404)
    return row


def _detail(conn, row):
    """Маягтыг асуулт, PDF, хариултын тоотой нь хамт буцаана."""
    return public_form(row,
                       questions=question_list(conn, row["id"]),
                       documents=document_list(conn, row["id"]),
                       total_responses=submission_count(conn, row["id"]))


def _detail_response(conn, fid, status=200):
    """Маягтын дэлгэрэнгүйг уншаад холболтыг хааж JSON хариу буцаана."""
    out = _detail(conn, get_form(conn, fid))
    conn.close()
    return jsonify(out), status


def _set_status(fid, status):
    """Маягтын төлөвийг (published / closed) солиод дэлгэрэнгүйг буцаана."""
    conn = get_db()
    require_form(conn, fid)
    if status == "published" and not conn.execute(
            "SELECT 1 FROM form_question WHERE form_id=?", (fid,)).fetchone():
        bad(conn, "Асуултгүй маягтыг нийтэлж болохгүй")
    update_row(conn, "form", fid, {"status": status, "updated_by": current_user_id(),
                                   "updated_at": now_str()})
    conn.commit()
    return _detail_response(conn, fid)
