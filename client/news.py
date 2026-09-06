"""Мэдээ, зарын ПОРТАЛ тал (Blueprint).

Замын угтвар: /api/portal/news... — НЭЭЛТТЭЙ (auth.py-ийн PUBLIC_PREFIXES):
зочин нэвтрэхгүйгээр мэдээг уншина. Зөвхөн `status='published'` мэдээ харагдана —
ноорог мэдээ 404 буцаана.

Админ тал (үүсгэх, блок барих, нийтлэх) нь admin/news.py дотор — тэнд токен + эрх шаардана.

Цэсний холбоо: `menu.news_category` нь тухайн "Мэдээ" төрлийн цэс аль ангиллыг
харуулахыг заана. Портал цэс дээр дарахад ?category=<тэр утга>-гаар дуудна;
цэсний news_category хоосон бол бүх ангиллыг харуулна.
"""
from flask import Blueprint, jsonify, request

from db import get_db
from news_core import (
    MAX_PER_PAGE, NEWS_CATEGORIES, bad, block_list, public_news, require_news,
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
        if category not in NEWS_CATEGORIES:
            bad(conn, "category буруу. Сонголт: " + ", ".join(NEWS_CATEGORIES))
        where.append("category=?")
        args.append(category)
    search = (request.args.get("search") or "").strip()
    if search:
        where.append("(title LIKE ? OR summary LIKE ?)")
        args += [f"%{search}%"] * 2
    clause = " WHERE " + " AND ".join(where)

    total = conn.execute("SELECT COUNT(*) FROM news" + clause, args).fetchone()[0]
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get("per_page", 12))))
    except ValueError:
        bad(conn, "page / per_page нь тоо байх ёстой")
    data = conn.execute(
        "SELECT * FROM news" + clause +
        " ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ? OFFSET ?",
        args + [per_page, (page - 1) * per_page]).fetchall()
    conn.close()
    return jsonify(data=[public_news(r) for r in data], total=total,
                   per_page=per_page, current_page=page,
                   pages=(total + per_page - 1) // per_page)


@bp.route("/api/portal/news/<int:nid>", methods=["GET"])
def get_news_detail(nid):
    """Нэг мэдээ `blocks`-той нь хамт. Ноорог мэдээнд 404."""
    conn = get_db()
    row = require_news(conn, nid, published_only=True)
    out = public_news(row, blocks=block_list(conn, nid))
    conn.close()
    return jsonify(out)
