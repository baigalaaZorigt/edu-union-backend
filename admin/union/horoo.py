"""horoo (Хороо) — CRUD."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import fail, json_body, pick, require, rows

from admin.union import bp
from admin.union.common import (_arg_filters, _create, _delete_by_id, _list_rows,
                                _purge_orphan_contacts, _purge_orphan_files,
                                _require_row, _update_by_id, _where)


# Хорооны талбарууд (holboo_id-аас бусад)
HOROO_FIELDS = ("name", "type", "registration_number", "founded_date")
NOT_FOUND = "Хороо олдсонгүй"


@bp.route("/api/horoo", methods=["GET"])
def list_horoo():
    cond, params = _arg_filters(("holboo_id",))
    return _list_rows("SELECT * FROM horoo" + _where(cond) + " ORDER BY id", params)


@bp.route("/api/horoo/<int:hid>", methods=["GET"])
def get_horoo(hid):
    conn = get_db()
    row = conn.execute("SELECT * FROM horoo WHERE id=?", (hid,)).fetchone()
    if not row:
        fail(conn, 404, NOT_FOUND)
    out = dict(row)
    out["contacts"] = rows(conn.execute(
        "SELECT * FROM contact WHERE owner_type='horoo' AND owner_id=? ORDER BY id",
        (hid,)).fetchall())
    conn.close()
    return jsonify(out)


@bp.route("/api/horoo", methods=["POST"])
def create_horoo():
    data = request.get_json(silent=True)
    require(data, ["holboo_id", "name"])
    conn = get_db()
    _require_row(conn, "holboo", data["holboo_id"], "holboo_id (эцэг холбоо) олдсонгүй")
    values = {"holboo_id": data["holboo_id"], **pick(data, HOROO_FIELDS, skip_none=True)}
    return _create(conn, "horoo", values, "SELECT * FROM horoo WHERE id=?")


@bp.route("/api/horoo/<int:hid>", methods=["PUT", "PATCH"])
def update_horoo(hid):
    values = pick(json_body(), HOROO_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(get_db(), "horoo", hid, values, NOT_FOUND)


@bp.route("/api/horoo/<int:hid>", methods=["DELETE"])
def delete_horoo(hid):
    return _delete_by_id(get_db(), "horoo", hid, NOT_FOUND,
                         _purge_orphan_contacts, _purge_orphan_files)
