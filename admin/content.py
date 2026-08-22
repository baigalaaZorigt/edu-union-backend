"""Порталын динамик цэс ба контентын CRUD (Blueprint).

Бүтэц:
  menu (Цэс) — порталын дээд цэс. `type` нь цэс дээр дарахад юу харагдахыг заана:
      page     — динамик контент хуудас (админ бүрэн удирдана)
      news / survey / poll / contact / home — кодод суусан функциональ хуудсууд
      external — зөвхөн external_url руу үсэрнэ
  page (Контент хуудас) — type='page' цэс бүрд НЭГ бичлэг (гарчиг, cover, төлөв).
  page_block (Блок) — хуудасны агуулга: text / image / video / file / link блокууд
      ЭРЭМБЭТЭЙГЭЭР дараалж, админ UI дээр ↑↓-ээр солигдоно.

Спекийн /api/page_image|page_file|page_video маршрутууд нь page_block дээрх
төрөлжсөн харагдац юм — өгөгдөл нэг хүснэгтэд (тиймээс нэг л эрэмбэ) хадгалагдана.
"""
import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, abort, send_from_directory

from db import get_db
from helpers import rows, require, json_body

bp = Blueprint("content", __name__)

# --- Байршуулсан файлын сан ---
# Зураг/файлыг эхлээд /api/upload руу илгээж, буцаж ирсэн URL-г блокод хадгална.
# CONTENT_UPLOAD_DIR орчны хувьсагчаар өөрчилнө (Render дээр тогтвортой disk руу заа).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.environ.get(
    "CONTENT_UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "content"))
UPLOAD_URL_PREFIX = "/uploads/content/"     # энэ URL-ээр буцаан үйлчилнэ (токенгүй)

MAX_IMAGE_SIZE = 5 * 1024 * 1024            # зураг ≤ 5 MB
MAX_DOC_SIZE = 20 * 1024 * 1024             # файл ≤ 20 MB

# Зөвшөөрөгдөх өргөтгөл -> MIME төрөл
IMAGE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp",
}
DOC_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Цэсний төрлүүд (спекийн хүснэгт). page-аас бусад нь кодод суусан функциональ хуудас.
MENU_TYPES = ("page", "news", "survey", "poll", "contact", "home", "external")

# Цэсний засаж/оруулж болох талбарууд (slug тусад нь боловсруулагдана)
MENU_FIELDS = ("parent_id", "title", "type", "sort_order", "is_visible", "external_url")

# Хуудасны засаж болох талбарууд
PAGE_FIELDS = ("title", "body", "cover_image", "status")
PAGE_STATUSES = ("published", "draft")

# Блокийн төрөл -> тухайн төрөлд хамаарах талбарууд (бусад багана NULL үлдэнэ)
BLOCK_FIELDS = {
    "text":  ("text",),
    "image": ("url", "caption"),
    "video": ("url", "title"),
    "file":  ("url", "name", "mime_type", "size"),
    "link":  ("url", "title"),
}
BLOCK_TYPES = tuple(BLOCK_FIELDS)

# Кирилл -> латин галиглал (slug автоматаар үүсгэхэд)
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ү": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


# ----------------------------- Туслахууд -----------------------------
def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        conn.close()
        abort(400, description="parent_id тоо байх ёстой")
    if mid is not None and parent_id == mid:
        conn.close()
        abort(400, description="Цэс өөрийгөө эцэг болгож болохгүй")
    parent = conn.execute("SELECT * FROM menu WHERE id=?", (parent_id,)).fetchone()
    if not parent:
        conn.close()
        abort(400, description="parent_id (эцэг цэс) олдсонгүй")
    if parent["parent_id"] is not None:
        conn.close()
        abort(400, description="Гүн 2 түвшин — дэд цэсний дэд цэс үүсгэхгүй")
    if mid is not None and conn.execute(
            "SELECT 1 FROM menu WHERE parent_id=?", (mid,)).fetchone():
        conn.close()
        abort(400, description="Дэд цэстэй цэсийг өөр цэсний доор оруулж болохгүй")
    return parent_id


def _validate_menu(conn, data, current=None):
    """type / is_visible / external_url-г шалгана (буруу бол conn хааж 400)."""
    mtype = data.get("type") or (current["type"] if current else None)
    if mtype and mtype not in MENU_TYPES:
        conn.close()
        abort(400, description="type буруу. Сонголт: " + ", ".join(MENU_TYPES))
    if mtype == "external":
        url = data.get("external_url",
                       current["external_url"] if current else None)
        if not url:
            conn.close()
            abort(400, description="type='external' үед external_url заавал")
    return mtype


def _next_sort(conn, table, column, value):
    """Тухайн эцэг доторх дараагийн эрэмбийн дугаар."""
    where = f"{column} IS NULL" if value is None else f"{column}=?"
    args = () if value is None else (value,)
    return (conn.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 FROM {table} WHERE {where}",
        args).fetchone()[0])


def _ensure_page(conn, menu_id, title):
    """type='page' цэсэнд хоосон page бичлэг үүсгэнэ (байхгүй бол)."""
    if conn.execute("SELECT 1 FROM page WHERE menu_id=?", (menu_id,)).fetchone():
        return
    conn.execute(
        "INSERT INTO page(menu_id, title, status, updated_at) VALUES (?,?,?,?)",
        (menu_id, title, "draft", _now()))


def _menu_row(conn, mid):
    """Цэсийг page_id-тай нь хамт буцаана (админ UI шууд хуудсыг нь нээхэд)."""
    return conn.execute(
        "SELECT m.*, p.id AS page_id FROM menu m "
        "LEFT JOIN page p ON p.menu_id = m.id WHERE m.id=?", (mid,)).fetchone()


def _tree(flat):
    """Хавтгай жагсаалтыг эцэг-хүүхдийн мод болгоно (children түлхүүртэйгээр)."""
    by_id = {r["id"]: dict(r, children=[]) for r in flat}
    roots = []
    for r in flat:
        node = by_id[r["id"]]
        parent = by_id.get(r["parent_id"])
        (parent["children"] if parent else roots).append(node)
    return roots


# ----------------------------- Блокийн туслахууд -----------------------------
def _public_block(row):
    """Блокийг төрөлдөө хамаарах талбаруудаар нь цэвэрхэн буцаана."""
    out = {"id": row["id"], "page_id": row["page_id"],
           "type": row["type"], "sort_order": row["sort_order"]}
    for f in BLOCK_FIELDS.get(row["type"], ()):
        out[f] = row[f]
    if row["type"] == "video":
        out["youtube_url"] = row["url"]      # спекийн нэршил
    return out


def _blocks_of(conn, page_id, btype=None):
    """Хуудасны блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    sql = "SELECT * FROM page_block WHERE page_id=?"
    args = [page_id]
    if btype:
        sql += " AND type=?"
        args.append(btype)
    sql += " ORDER BY sort_order, id"
    return [_public_block(r) for r in conn.execute(sql, args).fetchall()]


def _check_page(conn, page_id):
    """page_id байгаа эсэхийг шалгана (байхгүй бол 400)."""
    if not str(page_id).isdigit() or not conn.execute(
            "SELECT 1 FROM page WHERE id=?", (page_id,)).fetchone():
        conn.close()
        abort(400, description="page_id (эцэг хуудас) олдсонгүй")
    return int(page_id)


def _insert_block(conn, page_id, btype, values):
    """Блок нэмээд шинэ мөрийг нь буцаана (эрэмбийг автоматаар төгсгөлд тавина)."""
    cols = ["page_id", "type", "sort_order"]
    args = [page_id, btype, values.pop("sort_order", None)
            or _next_sort(conn, "page_block", "page_id", page_id)]
    for f in BLOCK_FIELDS[btype]:
        cols.append(f)
        args.append(values.get(f))
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO page_block({', '.join(cols)}) VALUES ({ph})", args)
    return conn.execute(
        "SELECT * FROM page_block WHERE id=?", (cur.lastrowid,)).fetchone()


def _remove_upload(url):
    """Бидний өөрсдийн байршуулсан файл бол дискнээс арилгана (гадаад URL-д хүрэхгүй)."""
    if not url or not url.startswith(UPLOAD_URL_PREFIX):
        return
    path = os.path.join(UPLOAD_DIR, os.path.basename(url))
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass    # диск дээрх файл арилгаж чадаагүй ч DB-гийн мөр устсан хэвээр


def _delete_block(bid, btype=None, label="Блок"):
    """Блокийг устгаад (хэрэв төрөл заасан бол зөвхөн тэр төрлийг) файлыг нь арилгана."""
    conn = get_db()
    sql = "SELECT * FROM page_block WHERE id=?"
    args = [bid]
    if btype:
        sql += " AND type=?"
        args.append(btype)
    row = conn.execute(sql, args).fetchone()
    if not row:
        conn.close()
        abort(404, description=f"{label} олдсонгүй")
    conn.execute("DELETE FROM page_block WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    _remove_upload(row["url"])
    return jsonify(deleted=bid)


# ============================ menu (Цэс) ============================
@bp.route("/api/menu", methods=["GET"])
def list_menu():
    """Бүх цэс. ?tree=1 -> мод хэлбэрээр, эс бөгөөс parent_id-тай хавтгай жагсаалт.

    Шүүлт: ?parent_id= (root бол 'null'), ?type=, ?is_visible=1
    """
    conn = get_db()
    sql = ("SELECT m.*, p.id AS page_id FROM menu m "
           "LEFT JOIN page p ON p.menu_id = m.id")
    where, args = [], []
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
        args.append(1 if request.args["is_visible"] in ("1", "true", "True") else 0)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY m.parent_id IS NOT NULL, m.parent_id, m.sort_order, m.id"
    data = rows(conn.execute(sql, args).fetchall())
    conn.close()
    if request.args.get("tree") in ("1", "true", "True"):
        return jsonify(_tree(data))
    return jsonify(data)


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
    slug = _unique_slug(conn, _slugify(data.get("slug") or data["title"]))
    now = _now()
    sort_order = data.get("sort_order") or _next_sort(conn, "menu", "parent_id", parent_id)
    try:
        cur = conn.execute(
            "INSERT INTO menu(parent_id, title, slug, type, sort_order, is_visible, "
            "external_url, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (parent_id, data["title"], slug, mtype, sort_order,
             1 if data.get("is_visible", True) else 0,
             data.get("external_url"), now, now))
    except Exception:
        conn.close()
        abort(409, description="Энэ slug аль хэдийн бүртгэгдсэн байна")
    if mtype == "page":
        _ensure_page(conn, cur.lastrowid, data["title"])
    conn.commit()
    row = _menu_row(conn, cur.lastrowid)
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/menu/reorder", methods=["PUT", "PATCH"])
def reorder_menu():
    """Drag-drop эрэмбийг бүхэлд нь хадгална.

    body: {"order": [{"id": 5, "parent_id": null, "sort_order": 1}, ...]}
    """
    data = json_body()
    order = data.get("order")
    if not isinstance(order, list) or not order:
        abort(400, description="order (жагсаалт) шаардлагатай")
    conn = get_db()
    updates = []
    for item in order:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            conn.close()
            abort(400, description="order доторх бичлэг бүр id-тай байна")
        mid = int(item["id"])
        if not conn.execute("SELECT 1 FROM menu WHERE id=?", (mid,)).fetchone():
            conn.close()
            abort(404, description=f"Цэс олдсонгүй: {mid}")
        updates.append((mid, item.get("parent_id"), item.get("sort_order", 0)))
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
        conn.close()
        abort(404, description="Цэс олдсонгүй")
    mtype = _validate_menu(conn, data, current)
    fields, values = [], []
    for f in MENU_FIELDS:
        if f not in data:
            continue
        val = data[f]
        if f == "parent_id":
            val = _check_parent(conn, val, mid)
        elif f == "is_visible":
            val = 1 if val else 0
        fields.append(f)
        values.append(val)
    if "slug" in data or "title" in data:
        base = _slugify(data.get("slug") or data.get("title"))
        fields.append("slug")
        values.append(_unique_slug(conn, base, mid))
    if not fields:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга")
    fields.append("updated_at")
    values.append(_now())
    values.append(mid)
    try:
        conn.execute(
            f"UPDATE menu SET {', '.join(f + '=?' for f in fields)} WHERE id=?", values)
    except Exception:
        conn.close()
        abort(409, description="Энэ slug аль хэдийн бүртгэгдсэн байна")
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
        _remove_upload(url)
    return jsonify(deleted=mid)


# ======================= page (Контент хуудас) =======================
@bp.route("/api/page/<int:menu_id>", methods=["GET"])
def get_page(menu_id):
    """Тухайн ЦЭСНИЙ контентыг блок/зураг/файл/видеотой нь буцаана.

    Анхаар: спекийн дагуу GET нь menu_id-аар, PUT нь page id-аар ажиллана.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM page WHERE menu_id=?", (menu_id,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Энэ цэсэнд контент хуудас алга")
    data = dict(row)
    data["blocks"] = _blocks_of(conn, row["id"])
    data["images"] = _blocks_of(conn, row["id"], "image")
    data["files"] = _blocks_of(conn, row["id"], "file")
    data["videos"] = _blocks_of(conn, row["id"], "video")
    conn.close()
    return jsonify(data)


@bp.route("/api/page", methods=["GET"])
def list_page():
    """Бүх контент хуудас (цэсний нэртэй нь). Админ жагсаалтад зориулав."""
    conn = get_db()
    data = rows(conn.execute(
        "SELECT p.*, m.title AS menu_title, m.slug AS menu_slug "
        "FROM page p JOIN menu m ON m.id = p.menu_id "
        "ORDER BY p.id").fetchall())
    conn.close()
    return jsonify(data)


def _validate_page(conn, data):
    status = data.get("status")
    if status and status not in PAGE_STATUSES:
        conn.close()
        abort(400, description="status буруу. Сонголт: " + ", ".join(PAGE_STATUSES))


@bp.route("/api/page", methods=["POST"])
def create_page():
    """Цэсэнд контент хуудас үүсгэх (type='page' цэсэнд нэг л удаа)."""
    data = request.get_json(silent=True)
    require(data, ["menu_id"])
    conn = get_db()
    _validate_page(conn, data)
    menu = conn.execute("SELECT * FROM menu WHERE id=?", (data["menu_id"],)).fetchone()
    if not menu:
        conn.close()
        abort(400, description="menu_id (цэс) олдсонгүй")
    if menu["type"] != "page":
        conn.close()
        abort(400, description="Зөвхөн type='page' цэсэнд контент хуудас үүсгэнэ")
    try:
        cur = conn.execute(
            "INSERT INTO page(menu_id, title, body, cover_image, status, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (menu["id"], data.get("title") or menu["title"], data.get("body"),
             data.get("cover_image"), data.get("status") or "draft", _now()))
    except Exception:
        conn.close()
        abort(409, description="Энэ цэсэнд контент хуудас аль хэдийн үүссэн байна")
    conn.commit()
    row = conn.execute("SELECT * FROM page WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/page/<int:pid>", methods=["PUT", "PATCH"])
def update_page(pid):
    """Контент засах (title, body, cover_image, status) — pid нь ХУУДСАНЫ id."""
    data = json_body()
    conn = get_db()
    _validate_page(conn, data)
    fields = [f for f in PAGE_FIELDS if f in data]
    if not fields:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга. Сонголт: " + ", ".join(PAGE_FIELDS))
    old = conn.execute("SELECT cover_image FROM page WHERE id=?", (pid,)).fetchone()
    cur = conn.execute(
        f"UPDATE page SET {', '.join(f + '=?' for f in fields)}, updated_at=? WHERE id=?",
        [data[f] for f in fields] + [_now(), pid])
    conn.commit()
    row = conn.execute("SELECT * FROM page WHERE id=?", (pid,)).fetchone()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Контент хуудас олдсонгүй")
    # Cover солигдвол хуучин зургийг дискнээс арилгана.
    if "cover_image" in data and old and old["cover_image"] != data["cover_image"]:
        _remove_upload(old["cover_image"])
    return jsonify(dict(row))


# ==================== page_block (Хуудасны блокууд) ====================
@bp.route("/api/page_block", methods=["GET"])
def list_page_block():
    """Блокууд. ?page_id= (эрэмбээрээ), ?type= -ээр шүүнэ."""
    conn = get_db()
    sql, args = "SELECT * FROM page_block", []
    where = []
    if request.args.get("page_id"):
        where.append("page_id=?")
        args.append(request.args["page_id"])
    if request.args.get("type"):
        where.append("type=?")
        args.append(request.args["type"])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY page_id, sort_order, id"
    data = [_public_block(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return jsonify(data)


@bp.route("/api/page_block/<int:bid>", methods=["GET"])
def get_page_block(bid):
    conn = get_db()
    row = conn.execute("SELECT * FROM page_block WHERE id=?", (bid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Блок олдсонгүй")
    return jsonify(_public_block(row))


@bp.route("/api/page_block", methods=["POST"])
def create_page_block():
    """Блок нэмэх: {page_id, type, ...төрлийн талбарууд}. Эрэмбэ төгсгөлд нэмэгдэнэ."""
    data = request.get_json(silent=True)
    require(data, ["page_id", "type"])
    btype = data["type"]
    if btype not in BLOCK_TYPES:
        abort(400, description="type буруу. Сонголт: " + ", ".join(BLOCK_TYPES))
    if btype != "text" and not data.get("url"):
        abort(400, description=f"type='{btype}' үед url заавал")
    conn = get_db()
    page_id = _check_page(conn, data["page_id"])
    row = _insert_block(conn, page_id, btype, dict(data))
    conn.commit()
    conn.close()
    return jsonify(_public_block(row)), 201


@bp.route("/api/page_block/reorder", methods=["PUT", "PATCH"])
def reorder_page_block():
    """Блокийн эрэмбийг хадгална: {"order": [{"id": 3, "sort_order": 1}, ...]}."""
    data = json_body()
    order = data.get("order")
    if not isinstance(order, list) or not order:
        abort(400, description="order (жагсаалт) шаардлагатай")
    conn = get_db()
    updates = []
    for item in order:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            conn.close()
            abort(400, description="order доторх бичлэг бүр id-тай байна")
        bid = int(item["id"])
        if not conn.execute("SELECT 1 FROM page_block WHERE id=?", (bid,)).fetchone():
            conn.close()
            abort(404, description=f"Блок олдсонгүй: {bid}")
        updates.append((item.get("sort_order", 0), bid))
    conn.executemany("UPDATE page_block SET sort_order=? WHERE id=?", updates)
    conn.commit()
    conn.close()
    return jsonify(updated=[b for _, b in updates])


@bp.route("/api/page_block/<int:bid>", methods=["PUT", "PATCH"])
def update_page_block(bid):
    """Блок засах — төрөлдөө хамаарах талбарууд + sort_order."""
    data = json_body()
    conn = get_db()
    row = conn.execute("SELECT * FROM page_block WHERE id=?", (bid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Блок олдсонгүй")
    allowed = BLOCK_FIELDS[row["type"]] + ("sort_order",)
    fields = [f for f in allowed if f in data]
    if not fields:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга. Сонголт: " + ", ".join(allowed))
    conn.execute(
        f"UPDATE page_block SET {', '.join(f + '=?' for f in fields)} WHERE id=?",
        [data[f] for f in fields] + [bid])
    conn.commit()
    new = conn.execute("SELECT * FROM page_block WHERE id=?", (bid,)).fetchone()
    conn.close()
    if "url" in fields and row["url"] != new["url"]:
        _remove_upload(row["url"])      # солигдсон хуучин файлыг арилгана
    return jsonify(_public_block(new))


@bp.route("/api/page_block/<int:bid>", methods=["DELETE"])
def delete_page_block(bid):
    return _delete_block(bid)


# ======== page_image / page_file / page_video (спекийн төрөлжсөн харагдац) ========
# Эдгээр нь page_block дээрх нимгэн бүрхүүл — өгөгдөл нэг хүснэгтэд хадгалагдана.
@bp.route("/api/page_image", methods=["GET"])
def list_page_image():
    return _list_typed("image")


@bp.route("/api/page_file", methods=["GET"])
def list_page_file():
    return _list_typed("file")


@bp.route("/api/page_video", methods=["GET"])
def list_page_video():
    return _list_typed("video")


def _list_typed(btype):
    conn = get_db()
    page_id = request.args.get("page_id")
    if page_id:
        data = _blocks_of(conn, page_id, btype)
    else:
        data = [_public_block(r) for r in conn.execute(
            "SELECT * FROM page_block WHERE type=? ORDER BY page_id, sort_order, id",
            (btype,)).fetchall()]
    conn.close()
    return jsonify(data)


@bp.route("/api/page_image", methods=["POST"])
def create_page_image():
    """{ page_id, url, caption } — галерейн зураг нэмэх."""
    data = request.get_json(silent=True)
    require(data, ["page_id", "url"])
    conn = get_db()
    page_id = _check_page(conn, data["page_id"])
    row = _insert_block(conn, page_id, "image", dict(data))
    conn.commit()
    conn.close()
    return jsonify(_public_block(row)), 201


@bp.route("/api/page_image/<int:bid>", methods=["DELETE"])
def delete_page_image(bid):
    return _delete_block(bid, "image", "Зураг")


@bp.route("/api/page_file", methods=["POST"])
def create_page_file():
    """{ page_id, url, name, mime_type, size } — татаж авах материал нэмэх."""
    data = request.get_json(silent=True)
    require(data, ["page_id", "url", "name"])
    conn = get_db()
    page_id = _check_page(conn, data["page_id"])
    row = _insert_block(conn, page_id, "file", dict(data))
    conn.commit()
    conn.close()
    return jsonify(_public_block(row)), 201


@bp.route("/api/page_file/<int:bid>", methods=["DELETE"])
def delete_page_file(bid):
    return _delete_block(bid, "file", "Файл")


@bp.route("/api/page_video", methods=["POST"])
def create_page_video():
    """{ page_id, youtube_url, title } — зөвхөн YouTube холбоос."""
    data = request.get_json(silent=True)
    require(data, ["page_id", "youtube_url"])
    url = data["youtube_url"]
    if "youtube.com" not in url and "youtu.be" not in url:
        abort(400, description="Зөвхөн YouTube холбоос оруулна")
    conn = get_db()
    page_id = _check_page(conn, data["page_id"])
    row = _insert_block(conn, page_id, "video", dict(data, url=url))
    conn.commit()
    conn.close()
    return jsonify(_public_block(row)), 201


@bp.route("/api/page_video/<int:bid>", methods=["DELETE"])
def delete_page_video(bid):
    return _delete_block(bid, "video", "Видео")


# ===================== upload (Файл байршуулах) =====================
def _validate_upload(f):
    """Өргөтгөл ба хэмжээг шалгаад (нэр, өргөтгөл, mime, хэмжээ)-г буцаана."""
    name = (f.filename or "").strip()
    if not name or "." not in name:
        abort(400, description="Файлын нэр буруу байна")
    ext = name.rsplit(".", 1)[1].lower()
    if ext in IMAGE_TYPES:
        mime, limit, label = IMAGE_TYPES[ext], MAX_IMAGE_SIZE, "Зураг 5 MB"
    elif ext in DOC_TYPES:
        mime, limit, label = DOC_TYPES[ext], MAX_DOC_SIZE, "Файл 20 MB"
    else:
        abort(400, description=(
            "Зөвшөөрөгдөөгүй төрөл. Зураг: " + ", ".join(IMAGE_TYPES) +
            " / Файл: " + ", ".join(DOC_TYPES)))
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        abort(400, description=f"'{name}': файл хоосон байна")
    if size > limit:
        abort(400, description=(
            f"'{name}': {label}-аас хэтэрсэн байна ({size / 1024 / 1024:.1f} MB)"))
    return name, ext, mime, size


@bp.route("/api/upload", methods=["POST"])
def upload():
    """multipart/form-data, `file` талбар -> {url, name, mime_type, size}.

    Буцаж ирсэн url-г page.cover_image эсвэл блокийн url талбарт хадгална.
    """
    f = (request.files.get("file") or
         (request.files.getlist("file") or [None])[0])
    if not f:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    name, ext, mime, size = _validate_upload(f)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_DIR, stored))
    return jsonify(url=UPLOAD_URL_PREFIX + stored,
                   name=name, mime_type=mime, size=size), 201


@bp.route("/uploads/content/<path:stored_name>", methods=["GET"])
def serve_upload(stored_name):
    """Байршуулсан файлыг үйлчилнэ — токен шаардахгүй (порталд <img>-ээр ачаална).

    auth.py-ийн PUBLIC_PREFIXES энэ замыг нээлттэй болгодог.
    """
    path = os.path.join(UPLOAD_DIR, os.path.basename(stored_name))
    if not os.path.isfile(path):
        abort(404, description="Файл олдсонгүй")
    return send_from_directory(UPLOAD_DIR, os.path.basename(stored_name))
