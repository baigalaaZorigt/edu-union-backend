"""Порталын нүүр хуудас — баннер ба хамтрагч байгууллага, АДМИН тал (Blueprint).

    GET    /api/banner              — бүх мөр (нуусан, хугацаа дууссан ч), sort_order, id
    GET    /api/banner/<id>
    POST   /api/banner              — {title, image_url, link_url, sort_order, is_visible,
                                       starts_at, ends_at}; image_url заавал
    PUT|PATCH /api/banner/<id>      — хэсэгчилсэн засвар
    DELETE /api/banner/<id>         — зураг нь /uploads/content/ дотор бол дискнээс ч арилна
    ... /api/partner                — ижил бүтэц: {name, url, icon, sort_order, is_visible}

Эрх: banner.* / partner.* (auth.py замын эхний сегментээс автоматаар гаргана).
Токенгүй порталын уншилт нь client/home.py-д. Шалгалт core/home_core.py-д.
"""
from flask import Blueprint, jsonify

from core.db import get_db
from core.helpers import fail, insert_row, json_body, update_row, fetch_page, list_json
from core.home_core import admin_row, validate_banner, validate_partner
from admin.content import remove_upload

bp = Blueprint("home_content", __name__)

NOT_FOUND = {"banner": "Баннер олдсонгүй", "partner": "Хамтрагч байгууллага олдсонгүй"}
VALIDATE = {"banner": validate_banner, "partner": validate_partner}


def _row(conn, table, rid):
    return conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()


def _list(table):
    conn = get_db()
    data, meta = fetch_page(conn, f"SELECT * FROM {table} ORDER BY sort_order, id")
    conn.close()
    return list_json([admin_row(r) for r in data], meta)


def _get(table, rid):
    conn = get_db()
    row = _row(conn, table, rid)
    if not row:
        fail(conn, 404, NOT_FOUND[table])
    conn.close()
    return jsonify(admin_row(row))


def _create(table):
    data = json_body()
    conn = get_db()
    rid = insert_row(conn, table, VALIDATE[table](conn, data))
    conn.commit()
    out = admin_row(_row(conn, table, rid))
    conn.close()
    return jsonify(out), 201


def _update(table, rid):
    data = json_body()
    conn = get_db()
    current = _row(conn, table, rid)
    if not current:
        fail(conn, 404, NOT_FOUND[table])
    values = VALIDATE[table](conn, data, current)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга")
    update_row(conn, table, rid, values)
    conn.commit()
    out = admin_row(_row(conn, table, rid))
    conn.close()
    # Баннерын зураг солигдвол хуучныг дискнээс арилгана (гадаад URL-д хүрэхгүй).
    if table == "banner" and "image_url" in values \
            and values["image_url"] != current["image_url"]:
        remove_upload(current["image_url"])
    return jsonify(out)


def _delete(table, rid):
    conn = get_db()
    row = _row(conn, table, rid)
    if not row:
        fail(conn, 404, NOT_FOUND[table])
    conn.execute(f"DELETE FROM {table} WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if table == "banner":
        remove_upload(row["image_url"])
    return jsonify(deleted=rid)


def _register(table):
    """/api/<table> CRUD маршрутуудыг бүртгэнэ (endpoint: list_banner, create_partner ...)."""
    base = f"/api/{table}"
    bp.add_url_rule(base, f"list_{table}", lambda: _list(table), methods=["GET"])
    bp.add_url_rule(base, f"create_{table}", lambda: _create(table), methods=["POST"])
    bp.add_url_rule(f"{base}/<int:rid>", f"get_{table}",
                    lambda rid: _get(table, rid), methods=["GET"])
    bp.add_url_rule(f"{base}/<int:rid>", f"update_{table}",
                    lambda rid: _update(table, rid), methods=["PUT", "PATCH"])
    bp.add_url_rule(f"{base}/<int:rid>", f"delete_{table}",
                    lambda rid: _delete(table, rid), methods=["DELETE"])


for _table in ("banner", "partner"):
    _register(_table)
