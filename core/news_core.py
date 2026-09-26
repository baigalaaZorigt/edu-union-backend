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
    out = {f: row[f] for f in ("id", "news_id", "type", "sort_order",
                               "created_at", "updated_at")}
    out.update({f: row[f] for f in BLOCK_FIELDS.get(row["type"], ())})
    if row["type"] == "video":
        out["youtube_url"] = row["url"]      # page_block-той ижил нэршил
    return out


def block_list(conn, news_id, btype=None):
    """Мэдээний блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    sql, args = "SELECT * FROM news_block WHERE news_id=?", [news_id]
    if btype:
        sql, args = sql + " AND type=?", args + [btype]
    return [public_block(r) for r in
            conn.execute(sql + " ORDER BY sort_order, id", args).fetchall()]


def public_news(row, **extra):
    """Мэдээг JSON болгоно. blocks зэргийг extra-гаар нэмж дамжуулна."""
    out = {f: row[f] for f in NEWS_COLUMNS}
    out.update(extra)
    return out


def news_page(conn, where, args, default_per_page):
    """`where` нөхцлүүдээр шүүсэн мэдээний нэг хуудас (?page= &per_page=).

    Нийтлэгдсэн огноогоор (байхгүй бол үүсгэсэн) шинэ нь эхэлж. Буцаалт нь мэдээний
    спекийн хэлбэр: {data, total, per_page, current_page, pages}. Холболтыг хаахгүй
    (алдаа гарвал л хаана).
    """
    clause = " WHERE " + " AND ".join(where)
    total = conn.execute("SELECT COUNT(*) FROM news" + clause, args).fetchone()[0]
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE,
                       max(1, int(request.args.get("per_page", default_per_page))))
    except ValueError:
        bad(conn, "page / per_page нь тоо байх ёстой")
    data = conn.execute(
        "SELECT * FROM news" + clause +
        " ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ? OFFSET ?",
        args + [per_page, (page - 1) * per_page]).fetchall()
    return dict(data=[public_news(r) for r in data], total=total,
                per_page=per_page, current_page=page,
                pages=(total + per_page - 1) // per_page)


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
