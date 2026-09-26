"""Санал хүсэлт, Өргөдөл гомдлын ПОРТАЛЫН тал (Blueprint).

Замын угтвар: /api/portal/... — auth.py-ийн PUBLIC_PREFIXES дотор тул
**ТОКЕНГҮЙ**: порталын зочин нэвтрэхгүйгээр маягтаа илгээнэ (судалгаа бөглөхтэй
яг ижил зарчим). Админы тал (жагсаалт, устгал) нь admin/feedback.py дотор.

Өргөдлийн хавсралт: файлыг эхлээд `POST /api/upload`-аар байршуулж (тэр нь
эрхтэй маршрут), буцаж ирсэн `url`-ийг `file_url` болгож ЭНД дамжуулна — шинэ
upload маршрут хэрэггүй (спек §3).
"""
from flask import Blueprint, jsonify, request

from core.db import get_db
from core.feedback_core import KINDS, insert, validate

bp = Blueprint("portal_feedback", __name__)


def _submit(kind):
    """Маягтыг шалгаад хадгална — хоёр төрөлд нэг л бие."""
    values = validate(None, kind, request.get_json(silent=True))
    conn = get_db()
    new_id = insert(conn, kind, values)
    conn.close()
    return jsonify(status=True, id=new_id, message=KINDS[kind]["ok_message"]), 201


@bp.route("/api/portal/suggestions", methods=["POST"])
def submit_suggestion():
    """Санал хүсэлт илгээх (Нэр, И-мэйл, Утас, Санал хүсэлт)."""
    return _submit("suggestions")


@bp.route("/api/portal/complaints", methods=["POST"])
def submit_complaint():
    """Өргөдөл, гомдол илгээх (+ хавсралт: file_url / file_name — заавал биш)."""
    return _submit("complaints")
