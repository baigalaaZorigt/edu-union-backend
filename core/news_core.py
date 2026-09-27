"""Мэдээ, зарын хуваалцсан цөм (admin + client site хоёулаа ашиглана).

Хүснэгтүүд (core/db.py-ийн SCHEMA_NEWS):
    news -> news_block

Энэ модуль нь ЗӨВХӨН домэйний логик: шалгалт, цэвэр хэлбэрт хөрвүүлэлт (public_*).
HTTP маршрутууд нь:
    admin/news.py   — /api/admin/news...   (админ: үүсгэх, блок барих, нийтлэх)
    client/news.py  — /api/portal/news...  (портал: жагсаалт, нээх — токенгүй)

Блокийн бүтэц нь admin/content.py-ийн page_block-той ЯГ ИЖИЛ (text/image/video/
file/link) — өөр хүснэгт учир талбарын жагсаалт нь энд тусад нь тодорхойлогдов.
"""
from flask import abort, request
from sqlalchemy import func, select

from core.orm import session
from core.orm.models import News, NewsBlock


# Мэдээний ангилал — цэс (menu.news_category) энэ утгаар шүүнэ
NEWS_CATEGORIES = ("Мэдээ", "Сургалт")
NEWS_STATUSES = ("draft", "published")

MAX_PER_PAGE = 100                         # хуудаслалтын дээд хэмжээ

# Оруулж/засаж болох талбарууд (published_at нь СЕРВЕР талд тавигдана)
NEWS_FIELDS = ("title", "category", "author", "cover_image_url", "summary", "status")

# Блокийн төрөл -> тухайн төрөлд хамаарах талбарууд (бусад багана NULL үлдэнэ).
# admin/content.py-ийн BLOCK_FIELDS-тэй ижил бүтэц, гэхдээ өөр хүснэгтийнх.
BLOCK_FIELDS = {
    "text":  ("text",),
    "image": ("url", "caption"),
    "video": ("url", "title"),
    "file":  ("url", "name", "mime_type", "size"),
    "link":  ("url", "title"),
}
BLOCK_TYPES = tuple(BLOCK_FIELDS)

# JSON-д гарах мэдээний баганууд (created_by/updated_by/deleted_at нь дотоод)
NEWS_COLUMNS = ("id", "title", "category", "author", "cover_image_url", "summary",
                "status", "published_at", "created_at", "updated_at")


def bad(message, code=400):
    """Алдаа шидэнэ (хүсэлтийн session-ийг teardown хаана)."""
    abort(code, description=message)


def check_category(value):
    """Ангиллыг шалгана — зөвхөн "Мэдээ" эсвэл "Сургалт"."""
    if value not in NEWS_CATEGORIES:
        bad("category буруу. Сонголт: " + ", ".join(NEWS_CATEGORIES))
    return value


def public_block(row):
    """Блокийг төрөлдөө хамаарах талбаруудаар нь цэвэрхэн буцаана."""
    out = {f: getattr(row, f) for f in ("id", "news_id", "type", "sort_order",
                                        "created_at", "updated_at")}
    out.update({f: getattr(row, f) for f in BLOCK_FIELDS.get(row.type, ())})
    if row.type == "video":
        out["youtube_url"] = row.url         # page_block-той ижил нэршил
    return out


def block_list(news_id, btype=None):
    """Мэдээний блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    stmt = select(NewsBlock).where(NewsBlock.news_id == news_id)
    if btype:
        stmt = stmt.where(NewsBlock.type == btype)
    stmt = stmt.order_by(NewsBlock.sort_order, NewsBlock.id)
    return [public_block(r) for r in session().scalars(stmt)]


def public_news(row, **extra):
    """Мэдээг JSON болгоно. blocks зэргийг extra-гаар нэмж дамжуулна."""
    out = {f: getattr(row, f) for f in NEWS_COLUMNS}
    out.update(extra)
    return out


def news_page(conds, default_per_page):
    """`conds` (ORM нөхцлүүд)-ээр шүүсэн мэдээний нэг хуудас (?page= &per_page=).

    Нийтлэгдсэн огноогоор (байхгүй бол үүсгэсэн) шинэ нь эхэлж. Буцаалт нь мэдээний
    спекийн хэлбэр: {data, total, per_page, current_page, pages}.
    """
    s = session()
    total = s.scalar(select(func.count()).select_from(News).where(*conds))
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE,
                       max(1, int(request.args.get("per_page", default_per_page))))
    except ValueError:
        bad("page / per_page нь тоо байх ёстой")
    data = s.scalars(
        select(News).where(*conds)
        .order_by(func.coalesce(News.published_at, News.created_at).desc(), News.id.desc())
        .limit(per_page).offset((page - 1) * per_page)).all()
    return dict(data=[public_news(r) for r in data], total=total,
                per_page=per_page, current_page=page,
                pages=(total + per_page - 1) // per_page)


def get_news(nid, published_only=False):
    """Мэдээг id-гаар авна (устгасныг тооцохгүй). Олдохгүй бол None."""
    stmt = select(News).where(News.id == nid, News.deleted_at.is_(None))
    if published_only:
        stmt = stmt.where(News.status == "published")
    return session().scalar(stmt)


def require_news(nid, published_only=False):
    """Мэдээг авна — олдохгүй бол 404."""
    row = get_news(nid, published_only)
    if row is None:
        bad("Мэдээ олдсонгүй", 404)
    return row
