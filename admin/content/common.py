"""Цэс/хуудас/блокийн хуваалцсан туслахууд (эрэмбэ, хоосон хуудас, блок нэмэх/устгах)."""

from datetime import datetime, timezone

from flask import jsonify, abort
from sqlalchemy import false, func, select

from core.helpers import json_body
from core.orm import session
from core.orm.models import Page, PageBlock

from admin.content.storage import remove_upload


# Блокийн төрөл -> тухайн төрөлд хамаарах талбарууд (бусад багана NULL үлдэнэ)
BLOCK_FIELDS = {
    "text":  ("text",),
    "image": ("url", "caption"),
    "video": ("url", "title"),
    "file":  ("url", "name", "mime_type", "size"),
    "link":  ("url", "title"),
}
BLOCK_TYPES = tuple(BLOCK_FIELDS)

# ?tree= / ?is_visible= зэрэг query-д "үнэн" гэж тооцох утгууд
_TRUE = ("1", "true", "True")


# ----------------------------- Туслахууд -----------------------------
def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _eq_arg(column, value):
    """Query string-ийн утгаар тоон баганыг шүүх нөхцөл (тоо биш бол юу ч таарахгүй)."""
    return column == int(value) if str(value).isdigit() else false()


def _next_sort(column, value):
    """Тухайн эцэг доторх дараагийн эрэмбийн дугаар (`column` нь эцгийн багана)."""
    model = column.class_
    cond = column.is_(None) if value is None else column == value
    return session().scalar(
        select(func.coalesce(func.max(model.sort_order), 0) + 1).where(cond))


def _ensure_page(menu_id, title):
    """type='page' цэсэнд хоосон page бичлэг үүсгэнэ (байхгүй бол)."""
    s = session()
    if s.scalar(select(Page.id).where(Page.menu_id == menu_id)) is not None:
        return
    s.add(Page(menu_id=menu_id, title=title, status="draft", updated_at=_now()))
    s.flush()


# ----------------------------- Блокийн туслахууд -----------------------------
def _public_block(block):
    """Блокийг төрөлдөө хамаарах талбаруудаар нь цэвэрхэн буцаана."""
    out = {"id": block.id, "page_id": block.page_id,
           "type": block.type, "sort_order": block.sort_order,
           "created_at": block.created_at, "updated_at": block.updated_at}
    for f in BLOCK_FIELDS.get(block.type, ()):
        out[f] = getattr(block, f)
    if block.type == "video":
        out["youtube_url"] = block.url      # спекийн нэршил
    return out


def _blocks_of(page_id, btype=None):
    """Хуудасны блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    stmt = select(PageBlock).where(PageBlock.page_id == page_id)
    if btype:
        stmt = stmt.where(PageBlock.type == btype)
    return [_public_block(b) for b in
            session().scalars(stmt.order_by(PageBlock.sort_order, PageBlock.id))]


def _check_page(page_id):
    """page_id байгаа эсэхийг шалгана (байхгүй бол 400)."""
    if not str(page_id).isdigit() or session().get(Page, int(page_id)) is None:
        abort(400, description="page_id (эцэг хуудас) олдсонгүй")
    return int(page_id)


def _insert_block(page_id, btype, values):
    """Блок нэмээд шинэ объектыг нь буцаана (эрэмбийг автоматаар төгсгөлд тавина)."""
    block = PageBlock(page_id=page_id, type=btype,
                      sort_order=values.get("sort_order")
                      or _next_sort(PageBlock.page_id, page_id),
                      **{f: values.get(f) for f in BLOCK_FIELDS[btype]})
    session().add(block)
    session().flush()
    return block


def _create_block(data, btype):
    """Шалгагдсан их биеэс блок нэмээд 201 хариу буцаана (page_block ба төрөлжсөн замууд)."""
    page_id = _check_page(data["page_id"])
    block = _insert_block(page_id, btype, data)
    session().commit()
    return jsonify(_public_block(block)), 201


def _delete_block(bid, btype=None, label="Блок"):
    """Блокийг устгаад (хэрэв төрөл заасан бол зөвхөн тэр төрлийг) файлыг нь арилгана."""
    s = session()
    block = s.get(PageBlock, bid)
    if block is None or (btype and block.type != btype):
        abort(404, description=f"{label} олдсонгүй")
    url = block.url
    s.delete(block)
    s.commit()
    remove_upload(url)
    return jsonify(deleted=bid)


def _order_items(model, label):
    """reorder-ийн {"order": [...]} их биеийг шалгана; [(объект, item), ...] буцаана.

    Бичлэг бүр тоон id-тай, DB дээр байгаа байх ёстой (эс бөгөөс 400 / 404).
    """
    order = json_body().get("order")
    if not isinstance(order, list) or not order:
        abort(400, description="order (жагсаалт) шаардлагатай")
    items = []
    for item in order:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            abort(400, description="order доторх бичлэг бүр id-тай байна")
        obj = session().get(model, int(item["id"]))
        if obj is None:
            abort(404, description=f"{label} олдсонгүй: {int(item['id'])}")
        items.append((obj, item))
    return items
