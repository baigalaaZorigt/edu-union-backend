"""page_block (Хуудасны блокууд) ба page_image|page_file|page_video төрөлжсөн харагдац."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import require, json_body, fail, pick, update_row

from admin.content import bp
from admin.content.storage import remove_upload
from admin.content.common import (BLOCK_FIELDS, BLOCK_TYPES, _blocks_of, _create_block,
                                  _delete_block, _order_items, _public_block)


# ==================== page_block (Хуудасны блокууд) ====================
@bp.route("/api/page_block", methods=["GET"])
def list_page_block():
    """Блокууд. ?page_id= (эрэмбээрээ), ?type= -ээр шүүнэ."""
    filters = [(col, request.args[col]) for col in ("page_id", "type")
               if request.args.get(col)]
    sql = "SELECT * FROM page_block"
    if filters:
        sql += " WHERE " + " AND ".join(f"{col}=?" for col, _ in filters)
    sql += " ORDER BY page_id, sort_order, id"
    conn = get_db()
    data = [_public_block(r)
            for r in conn.execute(sql, [v for _, v in filters]).fetchall()]
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
    return _create_block(data, btype)


@bp.route("/api/page_block/reorder", methods=["PUT", "PATCH"])
def reorder_page_block():
    """Блокийн эрэмбийг хадгална: {"order": [{"id": 3, "sort_order": 1}, ...]}."""
    conn, items = _order_items("page_block", "Блок")
    updates = [(item.get("sort_order", 0), bid) for bid, item in items]
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
        fail(conn, 404, "Блок олдсонгүй")
    allowed = BLOCK_FIELDS[row["type"]] + ("sort_order",)
    values = pick(data, allowed)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга. Сонголт: " + ", ".join(allowed))
    update_row(conn, "page_block", bid, values)
    conn.commit()
    new = conn.execute("SELECT * FROM page_block WHERE id=?", (bid,)).fetchone()
    conn.close()
    if "url" in values and row["url"] != new["url"]:
        remove_upload(row["url"])      # солигдсон хуучин файлыг арилгана
    return jsonify(_public_block(new))


@bp.route("/api/page_block/<int:bid>", methods=["DELETE"])
def delete_page_block(bid):
    return _delete_block(bid)


# ======== page_image / page_file / page_video (спекийн төрөлжсөн харагдац) ========
# Эдгээр нь page_block дээрх нимгэн бүрхүүл — өгөгдөл нэг хүснэгтэд хадгалагдана.
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


@bp.route("/api/page_image", methods=["GET"])
def list_page_image():
    return _list_typed("image")


@bp.route("/api/page_file", methods=["GET"])
def list_page_file():
    return _list_typed("file")


@bp.route("/api/page_video", methods=["GET"])
def list_page_video():
    return _list_typed("video")


@bp.route("/api/page_image", methods=["POST"])
def create_page_image():
    """{ page_id, url, caption } — галерейн зураг нэмэх."""
    data = request.get_json(silent=True)
    require(data, ["page_id", "url"])
    return _create_block(data, "image")


@bp.route("/api/page_image/<int:bid>", methods=["DELETE"])
def delete_page_image(bid):
    return _delete_block(bid, "image", "Зураг")


@bp.route("/api/page_file", methods=["POST"])
def create_page_file():
    """{ page_id, url, name, mime_type, size } — татаж авах материал нэмэх."""
    data = request.get_json(silent=True)
    require(data, ["page_id", "url", "name"])
    return _create_block(data, "file")


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
    return _create_block(dict(data, url=url), "video")


@bp.route("/api/page_video/<int:bid>", methods=["DELETE"])
def delete_page_video(bid):
    return _delete_block(bid, "video", "Видео")
