"""permission (Эрх) — CRUD."""
from flask import jsonify, request, abort
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from core.helpers import require, json_body, list_json
from core.orm import session
from core.orm.models import Permission
from core.orm.query import paginate

from admin.users import bp
from admin.users.common import _delete_by_id


ACTIONS = ("create", "read", "update", "delete")
PERMISSION_FIELDS = ("code", "name", "resource", "action", "description")


# ======================= permission (Эрх) =======================
PERMISSION_DUP = "Энэ code аль хэдийн бүртгэгдсэн байна"
NOT_FOUND = "Эрх олдсонгүй"


@bp.route("/api/permission", methods=["GET"])
def list_permission():
    stmt = select(Permission).order_by(Permission.id)
    resource = request.args.get("resource")
    if resource:
        stmt = stmt.where(Permission.resource == resource)
    items, meta = paginate(stmt)
    return list_json([p.to_dict() for p in items], meta)


@bp.route("/api/permission/<int:pid>", methods=["GET"])
def get_permission(pid):
    perm = session().get(Permission, pid)
    if perm is None:
        abort(404, description=NOT_FOUND)
    return jsonify(perm.to_dict())


def _validate_permission(data):
    act = data.get("action")
    if act and act not in ACTIONS:
        abort(400, description="action буруу. Сонголт: " + ", ".join(ACTIONS))


@bp.route("/api/permission", methods=["POST"])
def create_permission():
    data = request.get_json(silent=True)
    require(data, ["code", "name"])
    _validate_permission(data)
    s = session()
    perm = Permission(**{f: data.get(f) for f in PERMISSION_FIELDS})
    s.add(perm)
    try:
        s.commit()
    except SQLAlchemyError:
        s.rollback()
        abort(409, description=PERMISSION_DUP)
    return jsonify(perm.to_dict()), 201


@bp.route("/api/permission/<int:pid>", methods=["PUT", "PATCH"])
def update_permission(pid):
    data = json_body()
    _validate_permission(data)
    values = {f: data[f] for f in PERMISSION_FIELDS if f in data}
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    s = session()
    try:
        count = s.execute(update(Permission).where(Permission.id == pid).values(**values)).rowcount
        s.commit()
    except SQLAlchemyError:
        s.rollback()
        abort(409, description=PERMISSION_DUP)
    if count == 0:
        abort(404, description=NOT_FOUND)
    return jsonify(updated=pid, fields=list(values))


@bp.route("/api/permission/<int:pid>", methods=["DELETE"])
def delete_permission(pid):
    return _delete_by_id(Permission, pid, NOT_FOUND)
