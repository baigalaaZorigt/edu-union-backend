"""app_user (Хэрэглэгч) — CRUD."""
from flask import jsonify, request

from core.db import get_db
from core.helpers import require, json_body, fail, insert_row, update_row, fetch_page, list_json
from core.scope_core import public_scope

from admin.users import bp
from admin.users.common import (USER_SELECT, public_user, _delete_by_id, _exists, _hash,
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
def _check_user_refs(conn, data):
    """role_id / structure_id өгсөн (null биш) бол лавлахад байгаа эсэхийг шалгана."""
    for field, table, label in (("role_id", "role", "дүр"),
                                ("structure_id", "structure", "бүтцийн удирдлага")):
        if data.get(field) is not None and not _exists(conn, table, data[field]):
            fail(conn, 400, f"{field} ({label}) олдсонгүй")


@bp.route("/api/user", methods=["GET"])
def list_user():
    conn = get_db()
    # ?role_id= ба ?structure_id= шүүлтүүр — хосолж болно
    cond, params = [], []
    for f in ("role_id", "structure_id"):
        if request.args.get(f):
            cond.append(f"u.{f}=?")
            params.append(request.args[f])
    sql = USER_SELECT + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY u.id"
    page_rows, meta = fetch_page(conn, sql, params)
    data = [public_user(x) for x in page_rows]
    # Хамрах хүрээг шууд хамт өгнө — хэрэглэгч бүрээр /scope дуудах шаардлагагүй
    scopes = {r["user_id"]: public_scope(r)
              for r in conn.execute("SELECT * FROM user_scope").fetchall()}
    for u in data:
        u["scope"] = scopes.get(u["id"])
    conn.close()
    return list_json(data, meta)


@bp.route("/api/user/<int:uid>", methods=["GET"])
def get_user(uid):
    conn = get_db()
    row = _user_row(conn, uid)
    if not row:
        fail(conn, 404, "Хэрэглэгч олдсонгүй")
    out = _user_profile(conn, row)
    conn.close()
    return jsonify(out)


@bp.route("/api/user", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    conn = get_db()
    _check_user_refs(conn, data)
    try:
        uid = insert_row(conn, "app_user", {
            "username": data["username"],
            "password_hash": _hash(data["password"]),
            "last_name": data.get("last_name"),
            "first_name": data.get("first_name"),
            "email": data.get("email"),
            "role_id": data.get("role_id"),
            "structure_id": data.get("structure_id"),
            "is_active": 1 if data.get("is_active", 1) else 0,
            # Админ өгсөн анхны нууц үг (ихэвчлэн утасны дугаар) — хэрэглэгч
            # анх нэвтрэхэд ЗААВАЛ солино (спек §2). Хүсвэл 0-ээр дарж болно.
            "must_change_password": 1 if data.get("must_change_password", 1) else 0,
        })
        conn.commit()
    except Exception:
        fail(conn, 409, "Энэ нэвтрэх нэр аль хэдийн бүртгэгдсэн байна")
    row = _user_row(conn, uid)
    conn.close()
    return jsonify(public_user(row)), 201


@bp.route("/api/user/<int:uid>", methods=["PUT", "PATCH"])
def update_user(uid):
    data = json_body()
    conn = get_db()
    _check_user_refs(conn, data)
    # Логик талбаруудыг л 0/1 болгоно; бусдыг хэвээр нь дамжуулна
    values = {f: (1 if data[f] else 0) if f in BOOL_FIELDS else data[f]
              for f in USER_FIELDS if f in data}
    if data.get("password"):  # шинэ нууц үг өгвөл дахин hash хийнэ
        values["password_hash"] = _hash(data["password"])
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга")
    # Дүр СОЛИГДВОЛ хуучин хамрах хүрээ утгаа алддаг тул цэвэрлэнэ (спек §6)
    if "role_id" in data:
        old = conn.execute("SELECT role_id FROM app_user WHERE id=?", (uid,)).fetchone()
        if old and old["role_id"] != data["role_id"]:
            conn.execute("DELETE FROM user_scope WHERE user_id=?", (uid,))
    count = update_row(conn, "app_user", uid, values)
    conn.commit()
    if count == 0:
        fail(conn, 404, "Хэрэглэгч олдсонгүй")
    row = _user_row(conn, uid)
    conn.close()
    return jsonify(public_user(row))


@bp.route("/api/user/<int:uid>", methods=["DELETE"])
def delete_user(uid):
    return _delete_by_id("app_user", uid, "Хэрэглэгч олдсонгүй")
