"""Мэдээ, зарын хуваалцсан цөм (admin + client site хоёулаа ашиглана).

Хүснэгтүүд (db.py-ийн SCHEMA_NEWS):
    news -> news_block

Энэ модуль нь ЗӨВХӨН домэйний логик: шалгалт, цэвэр хэлбэрт хөрвүүлэлт (public_*).
HTTP маршрутууд нь:
    admin/news.py   — /api/admin/news...   (админ: үүсгэх, блок барих, нийтлэх)
    client/news.py  — /api/portal/news...  (портал: жагсаалт, нээх — токенгүй)

Блокийн бүтэц нь admin/content.py-ийн page_block-той ЯГ ИЖИЛ (text/image/video/
file/link) — өөр хүснэгт учир талбарын жагсаалт нь энд тусад нь тодорхойлогдов.
"""
from datetime import datetime, timezone

from flask import abort

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


def now_str():
    """Одоогийн UTC цаг — "YYYY-MM-DD HH:MM:SS" (form-ийн огноотой ижил хэлбэр)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def bad(conn, message, code=400):
    """Холболтыг хааж байгаад алдаа шидэнэ (холболт алдагдахаас сэргийлнэ)."""
    if conn is not None:
        conn.close()
    abort(code, description=message)


def check_category(conn, value):
    """Ангиллыг шалгана — зөвхөн "Мэдээ" эсвэл "Сургалт"."""
    if value not in NEWS_CATEGORIES:
        bad(conn, "category буруу. Сонголт: " + ", ".join(NEWS_CATEGORIES))
    return value


def public_block(row):
    """Блокийг төрөлдөө хамаарах талбаруудаар нь цэвэрхэн буцаана."""
    out = {"id": row["id"], "news_id": row["news_id"],
           "type": row["type"], "sort_order": row["sort_order"],
           "created_at": row["created_at"], "updated_at": row["updated_at"]}
    for f in BLOCK_FIELDS.get(row["type"], ()):
        out[f] = row[f]
    if row["type"] == "video":
        out["youtube_url"] = row["url"]      # page_block-той ижил нэршил
    return out


def block_list(conn, news_id, btype=None):
    """Мэдээний блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    sql = "SELECT * FROM news_block WHERE news_id=?"
    args = [news_id]
    if btype:
        sql += " AND type=?"
        args.append(btype)
    sql += " ORDER BY sort_order, id"
    return [public_block(r) for r in conn.execute(sql, args).fetchall()]


def public_news(row, **extra):
    """Мэдээг JSON болгоно. blocks зэргийг extra-гаар нэмж дамжуулна."""
    out = {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "author": row["author"],
        "cover_image_url": row["cover_image_url"],
        "summary": row["summary"],
        "status": row["status"],
        "published_at": row["published_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    out.update(extra)
    return out


def get_news(conn, nid, published_only=False):
    """Мэдээг id-гаар авна (устгасныг тооцохгүй). Олдохгүй бол None."""
    sql = "SELECT * FROM news WHERE id=? AND deleted_at IS NULL"
    if published_only:
        sql += " AND status='published'"
    return conn.execute(sql, (nid,)).fetchone()


def require_news(conn, nid, published_only=False):
    """Мэдээг авна — олдохгүй бол холболтыг хааж 404."""
    row = get_news(conn, nid, published_only)
    if not row:
        bad(conn, "Мэдээ олдсонгүй", 404)
    return row
