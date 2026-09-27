"""permission (Эрх) — CRUD."""
from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import rows, require, json_body, fail, insert_row, update_row, fetch_page, list_json

from admin.users import bp
from admin.users.common import _delete_by_id


ACTIONS = ("create", "read", "update", "delete")
PERMISSION_FIELDS = ("code", "name", "resource", "action", "description")


# ======================= permission (Эрх) =======================
PERMISSION_DUP = "Энэ code аль хэдийн бүртгэгдсэн байна"


@bp.route("/api/permission", methods=["GET"])
def list_permission():
    resource = request.args.get("resource")
    conn = get_db()
    if resource:
        data, meta = fetch_page(conn, "SELECT * FROM permission WHERE resource=? ORDER BY id",
                                (resource,))
    else:
        data, meta = fetch_page(conn, "SELECT * FROM permission ORDER BY id")
    conn.close()
    return list_json(rows(data), meta)


@bp.route("/api/permission/<int:pid>", methods=["GET"])
def get_permission(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM permission WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Эрх олдсонгүй")
    return jsonify(dict(row))


def _validate_permission(data):
    act = data.get("action")
    if act and act not in ACTIONS:
        abort(400, description="action буруу. Сонголт: " + ", ".join(ACTIONS))


@bp.route("/api/permission", methods=["POST"])
def create_permission():
    data = request.get_json(silent=True)
    require(data, ["code", "name"])
    _validate_permission(data)
    conn = get_db()
    try:
        pid = insert_row(conn, "permission", {f: data.get(f) for f in PERMISSION_FIELDS})
        conn.commit()
    except Exception:
        fail(conn, 409, PERMISSION_DUP)
    row = conn.execute("SELECT * FROM permission WHERE id=?", (pid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/permission/<int:pid>", methods=["PUT", "PATCH"])
def update_permission(pid):
    data = json_body()
    _validate_permission(data)
    values = {f: data[f] for f in PERMISSION_FIELDS if f in data}
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    try:
        count = update_row(conn, "permission", pid, values)
        conn.commit()
    except Exception:
        fail(conn, 409, PERMISSION_DUP)
    conn.close()
    if count == 0:
        abort(404, description="Эрх олдсонгүй")
    return jsonify(updated=pid, fields=list(values))


@bp.route("/api/permission/<int:pid>", methods=["DELETE"])
def delete_permission(pid):
    return _delete_by_id("permission", pid, "Эрх олдсонгүй")
