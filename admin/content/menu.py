"""menu (Цэс) — порталын 2 түвшний динамик цэс: CRUD, reorder, slug."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import rows, require, json_body, fail, insert_row, update_row, fetch_page, list_json

from admin.content import bp
from admin.content.storage import remove_upload
from admin.content.common import _TRUE, _ensure_page, _next_sort, _now, _order_items


# Цэсний төрлүүд (спекийн хүснэгт). page-аас бусад нь кодод суусан функциональ хуудас.
MENU_TYPES = ("page", "news", "survey", "poll", "contact", "home", "external")

# Цэсний засаж/оруулж болох талбарууд (slug тусад нь боловсруулагдана)
MENU_FIELDS = ("parent_id", "title", "type", "sort_order", "is_visible", "external_url",
               "news_category")

# type='news' цэс аль ангиллын мэдээг харуулахыг заана (news_core-той ижил жагсаалт).
# NULL = бүх ангилал (хуучин цэсүүд ингэж ажиллана).
NEWS_CATEGORIES = ("Мэдээ", "Сургалт")

# Кирилл -> латин галиглал (slug автоматаар үүсгэхэд)
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ү": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _slugify(text):
    """Гарчгаас URL-д тохирох slug гаргана (кирилл үсгийг галиглана)."""
    out = []
    for ch in (text or "").strip().lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append("-")
    slug = "-".join(part for part in "".join(out).split("-") if part)
    return slug[:80]


def _unique_slug(conn, base, mid=None):
    """Давхцахгүй slug буцаана — давхцвал -2, -3 ... гэж дугаарлана."""
    base = base or "menu"
    slug, n = base, 1
    while True:
        row = conn.execute("SELECT id FROM menu WHERE slug=?", (slug,)).fetchone()
        if not row or row["id"] == mid:
            return slug
        n += 1
        slug = f"{base}-{n}"


def _check_parent(conn, parent_id, mid=None):
    """Эцэг цэс зөв эсэхийг шалгана: байгаа, өөрөө биш, гүн 2 түвшнээс хэтрэхгүй."""
    if parent_id in (None, "", 0):
        return None
    try:
        parent_id = int(parent_id)
    except (TypeError, ValueError):
        fail(conn, 400, "parent_id тоо байх ёстой")
    if mid is not None and parent_id == mid:
        fail(conn, 400, "Цэс өөрийгөө эцэг болгож болохгүй")
    parent = conn.execute("SELECT * FROM menu WHERE id=?", (parent_id,)).fetchone()
    if not parent:
        fail(conn, 400, "parent_id (эцэг цэс) олдсонгүй")
    if parent["parent_id"] is not None:
        fail(conn, 400, "Гүн 2 түвшин — дэд цэсний дэд цэс үүсгэхгүй")
    if mid is not None and conn.execute(
            "SELECT 1 FROM menu WHERE parent_id=?", (mid,)).fetchone():
        fail(conn, 400, "Дэд цэстэй цэсийг өөр цэсний доор оруулж болохгүй")
    return parent_id


def _validate_menu(conn, data, current=None):
    """type / is_visible / external_url-г шалгана (буруу бол conn хааж 400)."""
    mtype = data.get("type") or (current["type"] if current else None)
    if mtype and mtype not in MENU_TYPES:
        fail(conn, 400, "type буруу. Сонголт: " + ", ".join(MENU_TYPES))
    if mtype == "external" and not data.get(
            "external_url", current["external_url"] if current else None):
        fail(conn, 400, "type='external' үед external_url заавал")
    if data.get("news_category"):
        if mtype != "news":
            fail(conn, 400, "news_category зөвхөн type='news' цэсэнд хамаарна")
        if data["news_category"] not in NEWS_CATEGORIES:
            fail(conn, 400, "news_category буруу. Сонголт: "
                 + ", ".join(NEWS_CATEGORIES) + " (эсвэл хоосон = бүгд)")
    return mtype


# Цэсийг page_id-тай нь хамт унших SELECT (админ UI шууд хуудсыг нь нээхэд)
MENU_SELECT = ("SELECT m.*, p.id AS page_id FROM menu m "
               "LEFT JOIN page p ON p.menu_id = m.id")


def _menu_row(conn, mid):
    """Цэсийг page_id-тай нь хамт буцаана."""
    return conn.execute(MENU_SELECT + " WHERE m.id=?", (mid,)).fetchone()


def _tree(flat):
    """Хавтгай жагсаалтыг эцэг-хүүхдийн мод болгоно (children түлхүүртэйгээр)."""
    by_id = {r["id"]: dict(r, children=[]) for r in flat}
    roots = []
    for r in flat:
        node = by_id[r["id"]]
        parent = by_id.get(r["parent_id"])
        (parent["children"] if parent else roots).append(node)
    return roots


# ============================ menu (Цэс) ============================
@bp.route("/api/menu", methods=["GET"])
def list_menu():
    """Бүх цэс. ?tree=1 -> мод хэлбэрээр, эс бөгөөс parent_id-тай хавтгай жагсаалт.

    Шүүлт: ?parent_id= (root бол 'null'), ?type=, ?is_visible=1
    """
    sql, where, args = MENU_SELECT, [], []
    parent_id = request.args.get("parent_id")
    if parent_id is not None:
        if parent_id in ("", "null", "0"):
            where.append("m.parent_id IS NULL")
        else:
            where.append("m.parent_id=?")
            args.append(parent_id)
    if request.args.get("type"):
        where.append("m.type=?")
        args.append(request.args["type"])
    if request.args.get("is_visible") is not None:
        where.append("m.is_visible=?")
        args.append(1 if request.args["is_visible"] in _TRUE else 0)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY m.parent_id IS NOT NULL, m.parent_id, m.sort_order, m.id"
    conn = get_db()
    if request.args.get("tree") in _TRUE:     # мод бүтэн байх ёстой — хуудаслахгүй
        data = rows(conn.execute(sql, args).fetchall())
        conn.close()
        return jsonify(_tree(data))
    data, meta = fetch_page(conn, sql, args)
    conn.close()
    return list_json(rows(data), meta)


@bp.route("/api/menu/<int:mid>", methods=["GET"])
def get_menu(mid):
    conn = get_db()
    row = _menu_row(conn, mid)
    conn.close()
    if not row:
        abort(404, description="Цэс олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/menu", methods=["POST"])
def create_menu():
    """Цэс нэмэх. slug байхгүй бол гарчгаас автоматаар үүснэ.

    type='page' үед хоосон page бичлэг дагаад үүснэ.
    """
    data = request.get_json(silent=True)
    require(data, ["title"])
    conn = get_db()
    mtype = _validate_menu(conn, data) or "page"
    parent_id = _check_parent(conn, data.get("parent_id"))
    now = _now()
    values = {
        "parent_id": parent_id, "title": data["title"],
        "slug": _unique_slug(conn, _slugify(data.get("slug") or data["title"])),
        "type": mtype,
        "sort_order": data.get("sort_order")
        or _next_sort(conn, "menu", "parent_id", parent_id),
        "is_visible": 1 if data.get("is_visible", True) else 0,
        "external_url": data.get("external_url"),
        "news_category": data.get("news_category") or None,
        "created_at": now, "updated_at": now,
    }
    try:
        mid = insert_row(conn, "menu", values)
    except Exception:
        fail(conn, 409, "Энэ slug аль хэдийн бүртгэгдсэн байна")
    if mtype == "page":
        _ensure_page(conn, mid, data["title"])
    conn.commit()
    row = _menu_row(conn, mid)
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/menu/reorder", methods=["PUT", "PATCH"])
def reorder_menu():
    """Drag-drop эрэмбийг бүхэлд нь хадгална.

    body: {"order": [{"id": 5, "parent_id": null, "sort_order": 1}, ...]}
    """
    conn, items = _order_items("menu", "Цэс")
    updates = [(mid, item.get("parent_id"), item.get("sort_order", 0))
               for mid, item in items]
    # Эцэг солигдох бол гүний шалгалт — бүх мөр DB дээр байгаа нь батлагдсаны дараа.
    for mid, parent_id, _ in updates:
        _check_parent(conn, parent_id, mid)
    now = _now()
    conn.executemany(
        "UPDATE menu SET parent_id=?, sort_order=?, updated_at=? WHERE id=?",
        [(p or None, s, now, m) for m, p, s in updates])
    conn.commit()
    conn.close()
    return jsonify(updated=[m for m, _, _ in updates])


@bp.route("/api/menu/<int:mid>", methods=["PUT", "PATCH"])
def update_menu(mid):
    """Цэс засах. type='page' болгож өөрчилвөл дутуу page бичлэг нөхөгдөнө."""
    data = json_body()
    conn = get_db()
    current = conn.execute("SELECT * FROM menu WHERE id=?", (mid,)).fetchone()
    if not current:
        fail(conn, 404, "Цэс олдсонгүй")
    mtype = _validate_menu(conn, data, current)
    values = {}
    for f in MENU_FIELDS:
        if f not in data:
            continue
        val = data[f]
        if f == "parent_id":
            val = _check_parent(conn, val, mid)
        elif f == "is_visible":
            val = 1 if val else 0
        elif f == "news_category":
            val = val or None       # хоосон = бүх ангилал
        values[f] = val
    if "slug" in data or "title" in data:
        base = _slugify(data.get("slug") or data.get("title"))
        values["slug"] = _unique_slug(conn, base, mid)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга")
    values["updated_at"] = _now()
    try:
        update_row(conn, "menu", mid, values)
    except Exception:
        fail(conn, 409, "Энэ slug аль хэдийн бүртгэгдсэн байна")
    if mtype == "page":
        _ensure_page(conn, mid, data.get("title") or current["title"])
    conn.commit()
    row = _menu_row(conn, mid)
    conn.close()
    return jsonify(dict(row))


@bp.route("/api/menu/<int:mid>", methods=["DELETE"])
def delete_menu(mid):
    """Цэс устгах — дэд цэс, page, блокууд нь бүгд хамт устна (cascade)."""
    conn = get_db()
    # Устахаас өмнө диск дээрх файлуудынх нь URL-г цуглуулна (дэд цэсийг оруулаад).
    urls = [r[0] for r in conn.execute(
        "WITH RECURSIVE sub(id) AS ("
        "  SELECT id FROM menu WHERE id=?"
        "  UNION ALL SELECT m.id FROM menu m JOIN sub ON m.parent_id = sub.id) "
        "SELECT b.url FROM page_block b JOIN page p ON p.id = b.page_id "
        "WHERE p.menu_id IN (SELECT id FROM sub) AND b.url IS NOT NULL "
        "UNION ALL "
        "SELECT p.cover_image FROM page p "
        "WHERE p.menu_id IN (SELECT id FROM sub) AND p.cover_image IS NOT NULL",
        (mid,)).fetchall()]
    cur = conn.execute("DELETE FROM menu WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Цэс олдсонгүй")
    for url in urls:
        remove_upload(url)
    return jsonify(deleted=mid)
