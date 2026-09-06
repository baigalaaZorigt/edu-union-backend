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

from db import get_db
from helpers import require, json_body
from admin.content import remove_upload
from news_core import (
    BLOCK_FIELDS, BLOCK_TYPES, MAX_PER_PAGE, NEWS_FIELDS, NEWS_STATUSES,
    bad, block_list, check_category, now_str, public_block, public_news, require_news,
)

bp = Blueprint("admin_news", __name__)


# ----------------------------- Туслахууд -----------------------------
def _user_id():
    """Одоо нэвтэрсэн хэрэглэгчийн id (created_by / updated_by-д бичнэ)."""
    user = getattr(g, "user", None)
    return user["id"] if user else None


def _check_status(conn, value):
    if value not in NEWS_STATUSES:
        bad(conn, "status буруу. Сонголт: " + ", ".join(NEWS_STATUSES))
    return value


def _next_sort(conn, news_id):
    """Тухайн мэдээн доторх дараагийн блокийн эрэмбэ."""
    return conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM news_block WHERE news_id=?",
        (news_id,)).fetchone()[0]


def _block_or_404(conn, bid):
    row = conn.execute("SELECT * FROM news_block WHERE id=?", (bid,)).fetchone()
    if not row:
        bad(conn, "Блок олдсонгүй", 404)
    return row


def _insert_block(conn, news_id, btype, values):
    """Блок нэмээд шинэ мөрийг нь буцаана (эрэмбийг автоматаар төгсгөлд тавина)."""
    cols = ["news_id", "type", "sort_order"]
    args = [news_id, btype,
            values.get("sort_order") or _next_sort(conn, news_id)]
    for f in BLOCK_FIELDS[btype]:
        cols.append(f)
        args.append(values.get(f))
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO news_block({', '.join(cols)}) VALUES ({ph})", args)
    return conn.execute(
        "SELECT * FROM news_block WHERE id=?", (cur.lastrowid,)).fetchone()


# ============================ news (Мэдээ) ============================
@bp.route("/api/admin/news", methods=["GET"])
def list_news():
    """Мэдээний жагсаалт. Шүүлт: ?search= &category= &status= &page= &per_page=

    Буцаалт (спекийн 5-р хэсэг): {data, total, per_page, current_page, pages}
    """
    conn = get_db()
    where, args = ["deleted_at IS NULL"], []
    if request.args.get("category"):
        where.append("category=?")
        args.append(request.args["category"])
    if request.args.get("status"):
        where.append("status=?")
        args.append(request.args["status"])
    search = (request.args.get("search") or "").strip()
    if search:
        where.append("(title LIKE ? OR summary LIKE ? OR author LIKE ?)")
        args += [f"%{search}%"] * 3
    clause = " WHERE " + " AND ".join(where)

    total = conn.execute("SELECT COUNT(*) FROM news" + clause, args).fetchone()[0]
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        bad(conn, "page / per_page нь тоо байх ёстой")
    # Нийтлэгдсэн нь эхэлж, дараа нь шинэ мэдээ дээшээ.
    data = conn.execute(
        "SELECT * FROM news" + clause +
        " ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ? OFFSET ?",
        args + [per_page, (page - 1) * per_page]).fetchall()
    conn.close()
    return jsonify(data=[public_news(r) for r in data], total=total,
                   per_page=per_page, current_page=page,
                   pages=(total + per_page - 1) // per_page)


@bp.route("/api/admin/news/<int:nid>", methods=["GET"])
def get_news_detail(nid):
    """Нэг мэдээ + `blocks` массив (эрэмбээрээ)."""
    conn = get_db()
    row = require_news(conn, nid)
    out = public_news(row, blocks=block_list(conn, nid))
    conn.close()
    return jsonify(out)


@bp.route("/api/admin/news", methods=["POST"])
def create_news():
    """Мэдээ үүсгэх. Заавал: title, category. Блокгүйгээр эхэлж үүснэ."""
    data = request.get_json(silent=True)
    require(data, ["title", "category"])
    conn = get_db()
    category = check_category(conn, data["category"])
    status = _check_status(conn, data.get("status") or "draft")
    now = now_str()
    cur = conn.execute(
        "INSERT INTO news(title, category, author, cover_image_url, summary, status, "
        "published_at, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (data["title"], category, data.get("author"), data.get("cover_image_url"),
         data.get("summary"), status,
         now if status == "published" else None,      # нийтэлмэгц огноог сервер тавина
         _user_id(), now, now))
    conn.commit()
    row = require_news(conn, cur.lastrowid)
    out = public_news(row, blocks=[])
    conn.close()
    return jsonify(out), 201


@bp.route("/api/admin/news/<int:nid>", methods=["PUT", "PATCH"])
def update_news(nid):
    """Мэдээ засах (хэсэгчилсэн). status='published' болгоход published_at тавигдана."""
    data = json_body()
    conn = get_db()
    current = require_news(conn, nid)
    if "category" in data:
        check_category(conn, data["category"])
    if "status" in data:
        _check_status(conn, data["status"])
    fields = [f for f in NEWS_FIELDS if f in data]
    if not fields:
        bad(conn, "Шинэчлэх талбар алга. Сонголт: " + ", ".join(NEWS_FIELDS))
    values = [data[f] for f in fields]
    now = now_str()
    # Ноорогоос нийтлэгдсэн рүү шилжихэд л published_at-г тавина (дахин нийтлэхэд
    # анхны огноо нь хадгалагдана — портал дээрх эрэмбэ хөдлөхгүй).
    if data.get("status") == "published" and not current["published_at"]:
        fields.append("published_at")
        values.append(now)
    conn.execute(
        f"UPDATE news SET {', '.join(f + '=?' for f in fields)}, "
        "updated_by=?, updated_at=? WHERE id=?", values + [_user_id(), now, nid])
    conn.commit()
    row = require_news(conn, nid)
    out = public_news(row, blocks=block_list(conn, nid))
    conn.close()
    # Ковер зураг солигдвол хуучныг дискнээс арилгана.
    if "cover_image_url" in data and current["cover_image_url"] != data["cover_image_url"]:
        remove_upload(current["cover_image_url"])
    return jsonify(out)


@bp.route("/api/admin/news/<int:nid>", methods=["DELETE"])
def delete_news(nid):
    """Мэдээг блокуудтай нь хамт устгана (cascade) — диск дээрх файлууд нь ч арилна."""
    conn = get_db()
    row = require_news(conn, nid)
    urls = [r[0] for r in conn.execute(
        "SELECT url FROM news_block WHERE news_id=? AND url IS NOT NULL",
        (nid,)).fetchall()]
    if row["cover_image_url"]:
        urls.append(row["cover_image_url"])
    conn.execute("DELETE FROM news WHERE id=?", (nid,))
    conn.commit()
    conn.close()
    for url in urls:
        remove_upload(url)
    return jsonify(deleted=nid)


# ====================== news_block (Мэдээний блокууд) ======================
@bp.route("/api/admin/news/<int:nid>/blocks", methods=["GET"])
def list_blocks(nid):
    """Тухайн мэдээний блокууд, эрэмбээрээ. ?type=-ээр шүүнэ."""
    conn = get_db()
    require_news(conn, nid)
    data = block_list(conn, nid, request.args.get("type"))
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/news/<int:nid>/blocks", methods=["POST"])
def create_block(nid):
    """Блок нэмэх: {type, ...төрлийн талбарууд}. Эрэмбэ төгсгөлд нэмэгдэнэ.

    video блокийг спекийн `youtube_url` нэрээр ч илгээж болно.
    """
    data = request.get_json(silent=True)
    require(data, ["type"])
    conn = get_db()
    require_news(conn, nid)
    btype = data["type"]
    if btype not in BLOCK_TYPES:
        bad(conn, "type буруу. Сонголт: " + ", ".join(BLOCK_TYPES))
    values = dict(data)
    if btype == "video" and not values.get("url"):
        values["url"] = values.get("youtube_url")
    if btype != "text" and not values.get("url"):
        bad(conn, f"type='{btype}' үед url заавал")
    row = _insert_block(conn, nid, btype, values)
    conn.commit()
    out = public_block(row)
    conn.close()
    return jsonify(out), 201


@bp.route("/api/admin/news/<int:nid>/blocks/reorder", methods=["PUT", "PATCH"])
def reorder_blocks(nid):
    """Блокийн эрэмбийг хадгална: {"order": [{"id": 501, "sort_order": 1}, ...]}."""
    data = json_body()
    order = data.get("order")
    if not isinstance(order, list) or not order:
        abort(400, description="order (жагсаалт) шаардлагатай")
    conn = get_db()
    require_news(conn, nid)
    updates = []
    for item in order:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            bad(conn, "order доторх бичлэг бүр id-тай байна")
        bid = int(item["id"])
        if not conn.execute("SELECT 1 FROM news_block WHERE id=? AND news_id=?",
                            (bid, nid)).fetchone():
            bad(conn, f"Энэ мэдээнд харьяалагдахгүй блок: {bid}", 404)
        updates.append((item.get("sort_order", 0), bid))
    conn.executemany("UPDATE news_block SET sort_order=? WHERE id=?", updates)
    conn.commit()
    conn.close()
    return jsonify(updated=[b for _, b in updates])


@bp.route("/api/admin/news_blocks/<int:bid>", methods=["GET"])
def get_block(bid):
    conn = get_db()
    row = _block_or_404(conn, bid)
    conn.close()
    return jsonify(public_block(row))


@bp.route("/api/admin/news_blocks/<int:bid>", methods=["PUT", "PATCH"])
def update_block(bid):
    """Блок засах — төрөлдөө хамаарах талбарууд + sort_order."""
    data = json_body()
    conn = get_db()
    row = _block_or_404(conn, bid)
    values = dict(data)
    if row["type"] == "video" and "youtube_url" in values and "url" not in values:
        values["url"] = values["youtube_url"]
    allowed = BLOCK_FIELDS[row["type"]] + ("sort_order",)
    fields = [f for f in allowed if f in values]
    if not fields:
        bad(conn, "Шинэчлэх талбар алга. Сонголт: " + ", ".join(allowed))
    conn.execute(
        f"UPDATE news_block SET {', '.join(f + '=?' for f in fields)} WHERE id=?",
        [values[f] for f in fields] + [bid])
    conn.commit()
    new = conn.execute("SELECT * FROM news_block WHERE id=?", (bid,)).fetchone()
    out = public_block(new)
    conn.close()
    if "url" in fields and row["url"] != new["url"]:
        remove_upload(row["url"])       # солигдсон хуучин файлыг арилгана
    return jsonify(out)


@bp.route("/api/admin/news_blocks/<int:bid>", methods=["DELETE"])
def delete_block(bid):
    conn = get_db()
    row = _block_or_404(conn, bid)
    conn.execute("DELETE FROM news_block WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    remove_upload(row["url"])
    return jsonify(deleted=bid)
