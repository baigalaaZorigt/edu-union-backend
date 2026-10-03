"""app_user (Хэрэглэгч) — CRUD + нууц үг сэргээх."""
from flask import abort, g, jsonify, request
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from core.helpers import require, json_body, list_json
from core.orm import session
from core.orm.models import AppUser, Role, Structure, UserScope
from core.orm.query import paginate
from core.scope_core import public_scope

from admin.users import bp
from admin.users.common import (public_user, user_select, _delete_by_id, _exists, _hash,
                                _user_profile, _user_row)


# Хэрэглэгчийн засаж/оруулж болох талбарууд (password, username-ээс бусад тусад нь).
# Нэр нь овог/нэр гэж ТУСДАА хадгалагдана (member-тэй ижил зарчим).
# `must_change_password`-ыг админ дахин 1 болгож, нууц үг сэргээсний дараа
# хэрэглэгчээс дахин солиулж болно.
USER_FIELDS = ("last_name", "first_name", "email", "role_id", "structure_id", "is_active",
               "must_change_password")
# DB-д 0/1 болж хадгалагдах логик талбарууд
BOOL_FIELDS = ("is_active", "must_change_password")


# ======================= app_user (Хэрэглэгч) =======================
NOT_FOUND = "Хэрэглэгч олдсонгүй"


def _check_user_refs(data):
    """role_id / structure_id өгсөн (null биш) бол лавлахад байгаа эсэхийг шалгана."""
    for field, model, label in (("role_id", Role, "дүр"),
                                ("structure_id", Structure, "бүтцийн удирдлага")):
        if data.get(field) is not None and not _exists(model, data[field]):
            abort(400, description=f"{field} ({label}) олдсонгүй")


@bp.route("/api/user", methods=["GET"])
def list_user():
    # ?role_id= ба ?structure_id= шүүлтүүр — хосолж болно
    stmt = user_select()
    for f in ("role_id", "structure_id"):
        if request.args.get(f):
            stmt = stmt.where(getattr(AppUser, f) == request.args[f])
    items, meta = paginate(stmt.order_by(AppUser.id), mappings=True)
    data = [public_user(x) for x in items]
    # Хамрах хүрээг шууд хамт өгнө — хэрэглэгч бүрээр /scope дуудах шаардлагагүй
    scopes = {r.user_id: public_scope(r.to_dict())
              for r in session().scalars(select(UserScope))}
    for u in data:
        u["scope"] = scopes.get(u["id"])
    return list_json(data, meta)


@bp.route("/api/user/<int:uid>", methods=["GET"])
def get_user(uid):
    row = _user_row(uid)
    if not row:
        abort(404, description=NOT_FOUND)
    return jsonify(_user_profile(row))


@bp.route("/api/user", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    _check_user_refs(data)
    s = session()
    user = AppUser(
        username=data["username"],
        password_hash=_hash(data["password"]),
        last_name=data.get("last_name"),
        first_name=data.get("first_name"),
        email=data.get("email"),
        role_id=data.get("role_id"),
        structure_id=data.get("structure_id"),
        is_active=1 if data.get("is_active", 1) else 0,
        # Админ өгсөн анхны нууц үг (ихэвчлэн утасны дугаар) — хэрэглэгч
        # анх нэвтрэхэд ЗААВАЛ солино (спек §2). Хүсвэл 0-ээр дарж болно.
        must_change_password=1 if data.get("must_change_password", 1) else 0,
    )
    s.add(user)
    try:
        s.commit()
    except SQLAlchemyError:
        s.rollback()
        abort(409, description="Энэ нэвтрэх нэр аль хэдийн бүртгэгдсэн байна")
    return jsonify(public_user(_user_row(user.id))), 201


@bp.route("/api/user/<int:uid>", methods=["PUT", "PATCH"])
def update_user(uid):
    data = json_body()
    _check_user_refs(data)
    # Логик талбаруудыг л 0/1 болгоно; бусдыг хэвээр нь дамжуулна
    values = {f: (1 if data[f] else 0) if f in BOOL_FIELDS else data[f]
              for f in USER_FIELDS if f in data}
    if data.get("password"):  # шинэ нууц үг өгвөл дахин hash хийнэ
        values["password_hash"] = _hash(data["password"])
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    s = session()
    # Дүр СОЛИГДВОЛ хуучин хамрах хүрээ утгаа алддаг тул цэвэрлэнэ (спек §6)
    if "role_id" in data:
        old = s.execute(select(AppUser.role_id).where(AppUser.id == uid)).first()
        if old is not None and old.role_id != data["role_id"]:
            s.execute(delete(UserScope).where(UserScope.user_id == uid))
    count = s.execute(update(AppUser).where(AppUser.id == uid).values(**values)).rowcount
    s.commit()
    if count == 0:
        abort(404, description=NOT_FOUND)
    return jsonify(public_user(_user_row(uid)))


@bp.route("/api/user/<int:uid>", methods=["DELETE"])
def delete_user(uid):
    return _delete_by_id(AppUser, uid, NOT_FOUND)


# Бүх хэрэглэгчийн нууц үгийг сэргээж чадах дүр: role.code = "1" (Super Admin) эсвэл
# seed-ийн бүх эрхтэй `admin` дүр (кодгүй).
SUPER_ROLE_CODE, SUPER_ROLE_NAME = "1", "admin"


def _is_super(user_id):
    row = _user_row(user_id)
    return bool(row) and (str(row["role_code"] or "").strip() == SUPER_ROLE_CODE
                          or row["role_name"] == SUPER_ROLE_NAME)


@bp.route("/api/user/<int:uid>/reset_password", methods=["POST"])
def reset_password(uid):
    """Нууц үгийг хэрэглэгчийн `username` (утасны дугаар) болгож, дахин солиулна.

    Зөвхөн Super Admin, эсвэл тэр бүртгэлийг ҮҮСГЭСЭН хүн (created_by) -> бусдад 403.
    Өмнө нь олгосон токенууд хүчингүй болно (token_version).
    """
    s = session()
    user = s.get(AppUser, uid)
    if user is None:
        abort(404, description=NOT_FOUND)
    if user.created_by != g.user["id"] and not _is_super(g.user["id"]):
        abort(403, description="Зөвхөн энэ хэрэглэгчийг бүртгэсэн хүн эсвэл Super Admin "
                               "нууц үгийг сэргээнэ")
    user.password_hash = _hash(user.username)
    user.must_change_password = 1
    user.token_version = (user.token_version or 0) + 1
    s.commit()
    return jsonify(status=True)
