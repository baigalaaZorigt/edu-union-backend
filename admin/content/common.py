"""Цэс/хуудас/блокийн хуваалцсан туслахууд (эрэмбэ, хоосон хуудас, блок нэмэх/устгах)."""

from datetime import datetime, timezone

from flask import jsonify, abort

from core.db import get_db
from core.helpers import json_body, fail, insert_row

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
    insert_row(conn, "page", {"menu_id": menu_id, "title": title,
                              "status": "draft", "updated_at": _now()})


# ----------------------------- Блокийн туслахууд -----------------------------
def _public_block(row):
    """Блокийг төрөлдөө хамаарах талбаруудаар нь цэвэрхэн буцаана."""
    out = {"id": row["id"], "page_id": row["page_id"],
           "type": row["type"], "sort_order": row["sort_order"],
           "created_at": row["created_at"], "updated_at": row["updated_at"]}
    for f in BLOCK_FIELDS.get(row["type"], ()):
        out[f] = row[f]
    if row["type"] == "video":
        out["youtube_url"] = row["url"]      # спекийн нэршил
    return out


def _block_query(column, value, btype=None):
    """`page_block`-ийг нэг баганаар (сонголтоор төрлөөр нь ч) шүүх SELECT + параметр."""
    sql, args = f"SELECT * FROM page_block WHERE {column}=?", [value]
    if btype:
        sql += " AND type=?"
        args.append(btype)
    return sql, args


def _blocks_of(conn, page_id, btype=None):
    """Хуудасны блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    sql, args = _block_query("page_id", page_id, btype)
    return [_public_block(r)
            for r in conn.execute(sql + " ORDER BY sort_order, id", args).fetchall()]


def _check_page(conn, page_id):
    """page_id байгаа эсэхийг шалгана (байхгүй бол 400)."""
    if not str(page_id).isdigit() or not conn.execute(
            "SELECT 1 FROM page WHERE id=?", (page_id,)).fetchone():
        fail(conn, 400, "page_id (эцэг хуудас) олдсонгүй")
    return int(page_id)


def _insert_block(conn, page_id, btype, values):
    """Блок нэмээд шинэ мөрийг нь буцаана (эрэмбийг автоматаар төгсгөлд тавина)."""
    row = {"page_id": page_id, "type": btype,
           "sort_order": values.get("sort_order")
           or _next_sort(conn, "page_block", "page_id", page_id)}
    row.update({f: values.get(f) for f in BLOCK_FIELDS[btype]})
    bid = insert_row(conn, "page_block", row)
    return conn.execute("SELECT * FROM page_block WHERE id=?", (bid,)).fetchone()


def _create_block(data, btype):
    """Шалгагдсан их биеэс блок нэмээд 201 хариу буцаана (page_block ба төрөлжсөн замууд)."""
    conn = get_db()
    page_id = _check_page(conn, data["page_id"])
    row = _insert_block(conn, page_id, btype, data)
    conn.commit()
    conn.close()
    return jsonify(_public_block(row)), 201


def _delete_block(bid, btype=None, label="Блок"):
    """Блокийг устгаад (хэрэв төрөл заасан бол зөвхөн тэр төрлийг) файлыг нь арилгана."""
    conn = get_db()
    row = conn.execute(*_block_query("id", bid, btype)).fetchone()
    if not row:
        fail(conn, 404, f"{label} олдсонгүй")
    conn.execute("DELETE FROM page_block WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    remove_upload(row["url"])
    return jsonify(deleted=bid)


def _order_items(table, label):
    """reorder-ийн {"order": [...]} их биеийг шалгана; (conn, [(id, item), ...]) буцаана.

    Бичлэг бүр тоон id-тай, DB дээр байгаа байх ёстой (эс бөгөөс 400 / 404).
    """
    order = json_body().get("order")
    if not isinstance(order, list) or not order:
        abort(400, description="order (жагсаалт) шаардлагатай")
    conn = get_db()
    items = []
    for item in order:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            fail(conn, 400, "order доторх бичлэг бүр id-тай байна")
        rid = int(item["id"])
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (rid,)).fetchone():
            fail(conn, 404, f"{label} олдсонгүй: {rid}")
        items.append((rid, item))
    return conn, items
