"""role (Дүр) — CRUD ба дүрд эрх нэмэх / хасах."""
from flask import jsonify, request, abort
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError

from core.helpers import require, json_body, list_json
from core.orm import session
from core.orm.models import AppUser, Permission, Role, RolePermission
from core.orm.query import paginate

from admin.users import bp
from admin.users.common import _delete_by_id, _exists, _role_perms, _role_perms_many

NOT_FOUND = "Дүр олдсонгүй"


def _role_out(rid):
    """Дүрийн мөр + эрхүүд."""
    out = session().get(Role, rid).to_dict()
    out["permissions"] = _role_perms(rid)
    return out


def _set_role_permissions(rid, permission_ids):
    """Дүрийн эрхийн жагсаалтыг бүхэлд нь солино (хуучныг устгаад шинээр оноох).

    Бүх id лавлахад байх ёстой (үгүй бол 400).
    """
    s = session()
    ids = list(dict.fromkeys(permission_ids))  # давхардлыг арилгана, дараалал хадгална
    if ids:
        found = s.scalar(select(func.count()).select_from(Permission)
                         .where(Permission.id.in_(ids)))
        if found != len(ids):
            abort(400, description="Зарим permission_id олдсонгүй")
    s.execute(delete(RolePermission).where(RolePermission.role_id == rid))
    s.add_all([RolePermission(role_id=rid, permission_id=pid) for pid in ids])
    s.flush()


# ======================= role (Дүр) =======================
ROLE_DUP = "Энэ дүрийн нэр аль хэдийн бүртгэгдсэн байна"
ROLE_FIELDS = ("name", "code", "description")


def _role_values(data, rid=None):
    """Ирсэн талбаруудаас хадгалах утгыг бэлтгэнэ; `code`-г шалгана.

    code нь заавал биш: хоосон мөр -> NULL. Хуучин DB-д багана ALTER-ээр нэмэгдсэн тул
    DB-д UNIQUE байхгүй — давхцлыг энд шалгана (409).
    """
    values = {f: data[f] for f in ROLE_FIELDS if f in data}
    if "code" in values:
        code = values["code"]
        if code is not None and not isinstance(code, str):
            abort(400, description="code нь текст байх ёстой")
        code = (code or "").strip() or None
        if code is not None and session().scalar(
                select(Role.id).where(Role.code == code, Role.id != (rid or 0))) is not None:
            abort(409, description=f"'{code}' кодтой дүр аль хэдийн бүртгэгдсэн байна")
        values["code"] = code
    return values


@bp.route("/api/role", methods=["GET"])
def list_role():
    items, meta = paginate(select(Role).order_by(Role.id))
    data = [r.to_dict() for r in items]
    perms = _role_perms_many([r["id"] for r in data])   # N+1 биш — нэг query
    for r in data:
        r["permissions"] = perms[r["id"]]
    return list_json(data, meta)


@bp.route("/api/role/<int:rid>", methods=["GET"])
def get_role(rid):
    if not _exists(Role, rid):
        abort(404, description=NOT_FOUND)
    out = _role_out(rid)
    out["user_count"] = session().scalar(
        select(func.count()).select_from(AppUser).where(AppUser.role_id == rid))
    return jsonify(out)


@bp.route("/api/role", methods=["POST"])
def create_role():
    data = request.get_json(silent=True)
    require(data, ["name"])
    s = session()
    role = Role(**_role_values(data))
    s.add(role)
    try:
        s.commit()
    except SQLAlchemyError:
        s.rollback()
        abort(409, description=ROLE_DUP)
    rid = role.id
    if isinstance(data.get("permission_ids"), list):
        _set_role_permissions(rid, data["permission_ids"])
        s.commit()
    return jsonify(_role_out(rid)), 201


@bp.route("/api/role/<int:rid>", methods=["PUT", "PATCH"])
def update_role(rid):
    data = json_body()
    s = session()
    if not _exists(Role, rid):
        abort(404, description=NOT_FOUND)
    values = _role_values(data, rid)
    if values:
        try:
            s.execute(update(Role).where(Role.id == rid).values(**values))
        except SQLAlchemyError:
            s.rollback()
            abort(409, description=ROLE_DUP)
    # permission_ids өгвөл эрхийн жагсаалтыг бүхэлд нь солино
    if isinstance(data.get("permission_ids"), list):
        _set_role_permissions(rid, data["permission_ids"])
    s.commit()
    return jsonify(_role_out(rid))


@bp.route("/api/role/<int:rid>", methods=["DELETE"])
def delete_role(rid):
    return _delete_by_id(Role, rid, NOT_FOUND)


# ---- Дүрд эрх нэг нэгээр нэмэх / хасах ----
@bp.route("/api/role/<int:rid>/permission", methods=["POST"])
def add_role_permission(rid):
    data = request.get_json(silent=True)
    require(data, ["permission_id"])
    s = session()
    if not _exists(Role, rid):
        abort(404, description=NOT_FOUND)
    pid = data["permission_id"]
    if not _exists(Permission, pid):
        abort(400, description="permission_id олдсонгүй")
    already = s.scalar(select(RolePermission.role_id).where(
        RolePermission.role_id == rid, RolePermission.permission_id == pid))
    if already is None:                        # давхар нэмэхгүй (хуучин "or ignore")
        s.add(RolePermission(role_id=rid, permission_id=pid))
        s.commit()
    return jsonify(role_id=rid, permissions=_role_perms(rid)), 201


@bp.route("/api/role/<int:rid>/permission/<int:pid>", methods=["DELETE"])
def remove_role_permission(rid, pid):
    s = session()
    count = s.execute(delete(RolePermission).where(
        RolePermission.role_id == rid, RolePermission.permission_id == pid)).rowcount
    s.commit()
    if count == 0:
        abort(404, description="Тухайн дүрд энэ эрх байхгүй байна")
    return jsonify(role_id=rid, removed_permission=pid)
