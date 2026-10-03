"""Мэдээ, зарын АДМИН тал (Blueprint).

Замын угтвар: /api/admin/news... — мэдээ үүсгэх, блокоор контент барих, нийтлэх.
Порталын тал (жагсаалт, нээх) нь client/news.py дотор — тэнд токен шаардахгүй.

Урсгал:
    Мэдээ үүсгэх (карт мэдээлэл: гарчиг, ангилал, ковер, товч)
      -> Блок нэмэх (текст / зураг / видео / файл / холбоос)
      -> Эрэмбэлэх (reorder)  -> status='published' болгож нийтлэх

Зураг/файлыг эхлээд `POST /api/upload` руу илгээж (admin/content.py), буцаж ирсэн
URL-г ковер эсвэл блокийн `url` талбарт хадгална — шинэ upload endpoint шаардлагагүй.
"""
from flask import Blueprint, jsonify, request, abort, g
from sqlalchemy import delete, func, select

from core.helpers import require, json_body, pick, now_str
from core.news_core import (
    BLOCK_FIELDS, BLOCK_TYPES, NEWS_FIELDS, NEWS_STATUSES, bad, block_list,
    check_category, news_page, public_block, public_news, require_news,
)
from core.orm import session
from core.orm.models import News, NewsBlock
from admin.content import remove_upload

bp = Blueprint("admin_news", __name__)


# ----------------------------- Туслахууд -----------------------------
def _user_id():
    """Одоо нэвтэрсэн хэрэглэгчийн id (created_by / updated_by-д бичнэ)."""
    user = getattr(g, "user", None)
    return user["id"] if user else None


def _check_status(value):
    if value not in NEWS_STATUSES:
        bad("status буруу. Сонголт: " + ", ".join(NEWS_STATUSES))
    return value


def _next_sort(news_id):
    """Тухайн мэдээн доторх дараагийн блокийн эрэмбэ."""
    return session().scalar(select(func.coalesce(func.max(NewsBlock.sort_order), 0) + 1)
                            .where(NewsBlock.news_id == news_id))


def _block_or_404(bid):
    row = session().get(NewsBlock, bid)
    if row is None:
        bad("Блок олдсонгүй", 404)
    return row


def _insert_block(news_id, btype, values):
    """Блок нэмээд шинэ объектыг нь буцаана (эрэмбийг автоматаар төгсгөлд тавина)."""
    block = NewsBlock(news_id=news_id, type=btype,
                      sort_order=values.get("sort_order") or _next_sort(news_id),
                      **{f: values.get(f) for f in BLOCK_FIELDS[btype]})
    session().add(block)
    return block


# ============================ news (Мэдээ) ============================
@bp.route("/api/admin/news", methods=["GET"])
def list_news():
    """Мэдээний жагсаалт. Шүүлт: ?search= &category= &status= &page= &per_page=

    Буцаалт (спекийн 5-р хэсэг): {data, total, per_page, current_page, pages}
    """
    conds = [News.deleted_at.is_(None)]
    if request.args.get("category"):
        conds.append(News.category == request.args["category"])
    if request.args.get("status"):
        conds.append(News.status == request.args["status"])
    search = (request.args.get("search") or "").strip()
    if search:
        pat = f"%{search}%"
        conds.append(News.title.ilike(pat) | News.summary.ilike(pat) | News.author.ilike(pat))
    return jsonify(news_page(conds, default_per_page=20, audit=True))


@bp.route("/api/admin/news/<int:nid>", methods=["GET"])
def get_news_detail(nid):
    """Нэг мэдээ + `blocks` массив (эрэмбээрээ)."""
    row = require_news(nid)
    return jsonify(public_news(row, audit=True, blocks=block_list(nid)))


@bp.route("/api/admin/news", methods=["POST"])
def create_news():
    """Мэдээ үүсгэх. Заавал: title, category. Блокгүйгээр эхэлж үүснэ."""
    data = request.get_json(silent=True)
    require(data, ["title", "category"])
    category = check_category(data["category"])
    status = _check_status(data.get("status") or "draft")
    now = now_str()
    news = News(title=data["title"], category=category, author=data.get("author"),
                cover_image_url=data.get("cover_image_url"), summary=data.get("summary"),
                status=status,
                published_at=now if status == "published" else None,  # огноог сервер тавина
                created_by=_user_id(), created_at=now, updated_at=now)
    s = session()
    s.add(news)
    s.commit()
    return jsonify(public_news(require_news(news.id), audit=True, blocks=[])), 201


@bp.route("/api/admin/news/<int:nid>", methods=["PUT", "PATCH"])
def update_news(nid):
    """Мэдээ засах (хэсэгчилсэн). status='published' болгоход published_at тавигдана."""
    data = json_body()
    current = require_news(nid)
    old_cover, old_published = current.cover_image_url, current.published_at
    if "category" in data:
        check_category(data["category"])
    if "status" in data:
        _check_status(data["status"])
    values = pick(data, NEWS_FIELDS)
    if not values:
        bad("Шинэчлэх талбар алга. Сонголт: " + ", ".join(NEWS_FIELDS))
    now = now_str()
    # Ноорогоос нийтлэгдсэн рүү шилжихэд л published_at-г тавина (дахин нийтлэхэд
    # анхны огноо нь хадгалагдана — портал дээрх эрэмбэ хөдлөхгүй).
    if data.get("status") == "published" and not old_published:
        values["published_at"] = now
    values.update(updated_by=_user_id(), updated_at=now)
    for k, v in values.items():
        setattr(current, k, v)
    session().commit()
    out = public_news(require_news(nid), audit=True, blocks=block_list(nid))
    # Ковер зураг солигдвол хуучныг дискнээс арилгана.
    if "cover_image_url" in data and old_cover != data["cover_image_url"]:
        remove_upload(old_cover)
    return jsonify(out)


@bp.route("/api/admin/news/<int:nid>", methods=["DELETE"])
def delete_news(nid):
    """Мэдээг блокуудтай нь хамт устгана (cascade) — диск дээрх файлууд нь ч арилна."""
    s = session()
    require_news(nid)
    s.execute(delete(News).where(News.id == nid))       # soft delete, блокууд каскадаар
    s.commit()
    return jsonify(deleted=nid)


# ====================== news_block (Мэдээний блокууд) ======================
@bp.route("/api/admin/news/<int:nid>/blocks", methods=["GET"])
def list_blocks(nid):
    """Тухайн мэдээний блокууд, эрэмбээрээ. ?type=-ээр шүүнэ."""
    require_news(nid)
    return jsonify(block_list(nid, request.args.get("type")))


@bp.route("/api/admin/news/<int:nid>/blocks", methods=["POST"])
def create_block(nid):
    """Блок нэмэх: {type, ...төрлийн талбарууд}. Эрэмбэ төгсгөлд нэмэгдэнэ.

    video блокийг спекийн `youtube_url` нэрээр ч илгээж болно.
    """
    data = request.get_json(silent=True)
    require(data, ["type"])
    require_news(nid)
    btype = data["type"]
    if btype not in BLOCK_TYPES:
        bad("type буруу. Сонголт: " + ", ".join(BLOCK_TYPES))
    values = dict(data)
    if btype == "video" and not values.get("url"):
        values["url"] = values.get("youtube_url")
    if btype != "text" and not values.get("url"):
        bad(f"type='{btype}' үед url заавал")
    block = _insert_block(nid, btype, values)
    session().commit()
    return jsonify(public_block(block)), 201


@bp.route("/api/admin/news/<int:nid>/blocks/reorder", methods=["PUT", "PATCH"])
def reorder_blocks(nid):
    """Блокийн эрэмбийг хадгална: {"order": [{"id": 501, "sort_order": 1}, ...]}."""
    data = json_body()
    order = data.get("order")
    if not isinstance(order, list) or not order:
        abort(400, description="order (жагсаалт) шаардлагатай")
    require_news(nid)
    s = session()
    updates = []
    for item in order:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            bad("order доторх бичлэг бүр id-тай байна")
        bid = int(item["id"])
        block = s.scalar(select(NewsBlock).where(NewsBlock.id == bid, NewsBlock.news_id == nid))
        if block is None:
            bad(f"Энэ мэдээнд харьяалагдахгүй блок: {bid}", 404)
        updates.append((block, item.get("sort_order", 0)))
    for block, sort in updates:
        block.sort_order = sort
    s.commit()
    return jsonify(updated=[b.id for b, _ in updates])


@bp.route("/api/admin/news_blocks/<int:bid>", methods=["GET"])
def get_block(bid):
    return jsonify(public_block(_block_or_404(bid)))


@bp.route("/api/admin/news_blocks/<int:bid>", methods=["PUT", "PATCH"])
def update_block(bid):
    """Блок засах — төрөлдөө хамаарах талбарууд + sort_order."""
    data = json_body()
    block = _block_or_404(bid)
    old_url = block.url
    values = dict(data)
    if block.type == "video" and "youtube_url" in values and "url" not in values:
        values["url"] = values["youtube_url"]
    allowed = BLOCK_FIELDS[block.type] + ("sort_order",)
    changes = pick(values, allowed)
    if not changes:
        bad("Шинэчлэх талбар алга. Сонголт: " + ", ".join(allowed))
    for k, v in changes.items():
        setattr(block, k, v)
    session().commit()
    out = public_block(block)
    if "url" in changes and old_url != block.url:
        remove_upload(old_url)          # солигдсон хуучин файлыг арилгана
    return jsonify(out)


@bp.route("/api/admin/news_blocks/<int:bid>", methods=["DELETE"])
def delete_block(bid):
    s = session()
    s.delete(_block_or_404(bid))
    s.commit()
    return jsonify(deleted=bid)
