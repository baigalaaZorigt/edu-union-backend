"""Мэдээ, зарын ПОРТАЛ тал (Blueprint).

Замын угтвар: /api/portal/news... — НЭЭЛТТЭЙ (core/auth.py-ийн PUBLIC_PREFIXES):
зочин нэвтрэхгүйгээр мэдээг уншина. Зөвхөн `status='published'` мэдээ харагдана —
ноорог мэдээ 404 буцаана.

Админ тал (үүсгэх, блок барих, нийтлэх) нь admin/news.py дотор — тэнд токен + эрх шаардана.

Цэсний холбоо: `menu.news_category` нь тухайн "Мэдээ" төрлийн цэс аль ангиллыг
харуулахыг заана. Портал цэс дээр дарахад ?category=<тэр утга>-гаар дуудна;
цэсний news_category хоосон бол бүх ангиллыг харуулна.
"""
from flask import Blueprint, jsonify, request

from core.db import get_db
from core.news_core import (
    block_list, check_category, news_page, public_news, require_news,
)

bp = Blueprint("portal_news", __name__)


@bp.route("/api/portal/news", methods=["GET"])
def list_news():
    """Нийтлэгдсэн мэдээний картлаг жагсаалт.

    Шүүлт: ?category=Мэдээ|Сургалт (өгөөгүй бол бүгд), ?search=, ?page=, ?per_page=
    Буцаалт: {data, total, per_page, current_page, pages}
    """
    conn = get_db()
    where, args = ["deleted_at IS NULL", "status='published'"], []
    category = request.args.get("category")
    if category:
        where.append("category=?")
        args.append(check_category(conn, category))
    search = (request.args.get("search") or "").strip()
    if search:
        where.append("(title LIKE ? OR summary LIKE ?)")
        args += [f"%{search}%"] * 2
    out = news_page(conn, where, args, default_per_page=12)
    conn.close()
    return jsonify(out)


@bp.route("/api/portal/news/<int:nid>", methods=["GET"])
def get_news_detail(nid):
    """Нэг мэдээ `blocks`-той нь хамт. Ноорог мэдээнд 404."""
    conn = get_db()
    row = require_news(conn, nid, published_only=True)
    out = public_news(row, blocks=block_list(conn, nid))
    conn.close()
    return jsonify(out)
