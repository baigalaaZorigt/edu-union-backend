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

from core.news_core import (
    block_list, check_category, news_page, public_news, require_news,
)
from core.orm.models import News

bp = Blueprint("portal_news", __name__)


@bp.route("/api/portal/news", methods=["GET"])
def list_news():
    """Нийтлэгдсэн мэдээний картлаг жагсаалт.

    Шүүлт: ?category=Мэдээ|Сургалт (өгөөгүй бол бүгд), ?search=, ?page=, ?per_page=
    Буцаалт: {data, total, per_page, current_page, pages}
    """
    conds = [News.deleted_at.is_(None), News.status == "published"]
    category = request.args.get("category")
    if category:
        conds.append(News.category == check_category(category))
    search = (request.args.get("search") or "").strip()
    if search:
        pat = f"%{search}%"
        conds.append(News.title.ilike(pat) | News.summary.ilike(pat))
    return jsonify(news_page(conds, default_per_page=12))


@bp.route("/api/portal/news/<int:nid>", methods=["GET"])
def get_news_detail(nid):
    """Нэг мэдээ `blocks`-той нь хамт. Ноорог мэдээнд 404."""
    row = require_news(nid, published_only=True)
    return jsonify(public_news(row, blocks=block_list(nid)))
