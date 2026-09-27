"""page_block (Хуудасны блокууд) ба page_image|page_file|page_video төрөлжсөн харагдац."""

from flask import jsonify, request, abort
from sqlalchemy import select

from core.helpers import require, json_body, pick, list_json
from core.orm import session
from core.orm.models import PageBlock
from core.orm.query import paginate

from admin.content import bp
from admin.content.storage import remove_upload
from admin.content.common import (BLOCK_FIELDS, BLOCK_TYPES, _create_block,
                                  _delete_block, _eq_arg, _order_items, _public_block)

BLOCK_ORDER = (PageBlock.page_id, PageBlock.sort_order, PageBlock.id)


# ==================== page_block (Хуудасны блокууд) ====================
@bp.route("/api/page_block", methods=["GET"])
def list_page_block():
    """Блокууд. ?page_id= (эрэмбээрээ), ?type= -ээр шүүнэ."""
    stmt = select(PageBlock)
    if request.args.get("page_id"):
        stmt = stmt.where(_eq_arg(PageBlock.page_id, request.args["page_id"]))
    if request.args.get("type"):
        stmt = stmt.where(PageBlock.type == request.args["type"])
    blocks, meta = paginate(stmt.order_by(*BLOCK_ORDER))
    return list_json([_public_block(b) for b in blocks], meta)


@bp.route("/api/page_block/<int:bid>", methods=["GET"])
def get_page_block(bid):
    block = session().get(PageBlock, bid)
    if block is None:
        abort(404, description="Блок олдсонгүй")
    return jsonify(_public_block(block))


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
    items = _order_items(PageBlock, "Блок")
    for block, item in items:
        block.sort_order = item.get("sort_order", 0)
    ids = [b.id for b, _ in items]
    session().commit()
    return jsonify(updated=ids)


@bp.route("/api/page_block/<int:bid>", methods=["PUT", "PATCH"])
def update_page_block(bid):
    """Блок засах — төрөлдөө хамаарах талбарууд + sort_order."""
    data = json_body()
    block = session().get(PageBlock, bid)
    if block is None:
        abort(404, description="Блок олдсонгүй")
    allowed = BLOCK_FIELDS[block.type] + ("sort_order",)
    values = pick(data, allowed)
    if not values:
        abort(400, description="Шинэчлэх талбар алга. Сонголт: " + ", ".join(allowed))
    old_url = block.url
    for f, v in values.items():
        setattr(block, f, v)
    session().commit()
    if "url" in values and old_url != block.url:
        remove_upload(old_url)      # солигдсон хуучин файлыг арилгана
    return jsonify(_public_block(block))


@bp.route("/api/page_block/<int:bid>", methods=["DELETE"])
def delete_page_block(bid):
    return _delete_block(bid)


# ======== page_image / page_file / page_video (спекийн төрөлжсөн харагдац) ========
# Эдгээр нь page_block дээрх нимгэн бүрхүүл — өгөгдөл нэг хүснэгтэд хадгалагдана.
def _list_typed(btype):
    stmt = select(PageBlock).where(PageBlock.type == btype)
    if request.args.get("page_id"):
        stmt = stmt.where(_eq_arg(PageBlock.page_id, request.args["page_id"]))
    blocks, meta = paginate(stmt.order_by(*BLOCK_ORDER))
    return list_json([_public_block(b) for b in blocks], meta)


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
