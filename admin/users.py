"""Хэрэглэгчийн удирдлагын CRUD (Blueprint).

Бүтэц:
  permission (Эрх)  — CRUD үйлдэл бүр нэг эрх (ж: 'user.create')
  role (Дүр)        — role_permission-оор дамжуулан ОЛОН эрхтэй (M:N)
  app_user (Хэрэглэгч) — role_id-аар нэг дүр СОНГОЖ, дүрийнхээ бүх эрхийг удамшуулна
"""
from flask import Blueprint, jsonify, request, abort
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db
from helpers import rows, require, json_body

bp = Blueprint("users", __name__)

ACTIONS = ("create", "read", "update", "delete")

# Хэрэглэгчийн засаж/оруулж болох талбарууд (password, username-ээс бусад тусад нь)
USER_FIELDS = ("full_name", "email", "role_id", "is_active")


# ----------------------------- Туслахууд -----------------------------
def public_user(row):
    """Хэрэглэгчийн мөрөөс password_hash-г хасаад буцаана."""
    d = dict(row)
    d.pop("password_hash", None)
    return d


def _role_perms(conn, rid):
    """Тухайн дүрийн бүх эрхийг буцаана."""
    return rows(conn.execute(
        "SELECT p.* FROM role_permission rp "
        "JOIN permission p ON p.id = rp.permission_id "
        "WHERE rp.role_id=? ORDER BY p.id", (rid,)).fetchall())


def _check_permissions_exist(conn, permission_ids):
    """permission_ids доторх бүх id лавлахад байгаа эсэхийг шалгана."""
    ids = list(dict.fromkeys(permission_ids))  # давхардлыг арилгана, дараалал хадгална
    if not ids:
        return ids
    ph = ", ".join("?" * len(ids))
    found = conn.execute(
        f"SELECT COUNT(*) FROM permission WHERE id IN ({ph})", ids).fetchone()[0]
    if found != len(ids):
        conn.close()
        abort(400, description="Зарим permission_id олдсонгүй")
    return ids


def _set_role_permissions(conn, rid, permission_ids):
    """Дүрийн эрхийн жагсаалтыг бүхэлд нь солино (хуучныг устгаад шинээр оноох)."""
    ids = _check_permissions_exist(conn, permission_ids)
    conn.execute("DELETE FROM role_permission WHERE role_id=?", (rid,))
    conn.executemany(
        "INSERT OR IGNORE INTO role_permission(role_id, permission_id) VALUES (?, ?)",
        [(rid, pid) for pid in ids])


# 400/404/409 алдааны JSON хариу нь run.py дотор app-түвшинд төвлөрсөн.


# ======================= permission (Эрх) =======================
@bp.route("/api/permission", methods=["GET"])
def list_permission():
    resource = request.args.get("resource")
    conn = get_db()
    if resource:
        data = rows(conn.execute(
            "SELECT * FROM permission WHERE resource=? ORDER BY id", (resource,)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM permission ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


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
        cur = conn.execute(
            "INSERT INTO permission(code, name, resource, action, description) "
            "VALUES (?,?,?,?,?)",
            (data["code"], data["name"], data.get("resource"),
             data.get("action"), data.get("description")))
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ code аль хэдийн бүртгэгдсэн байна")
    row = conn.execute("SELECT * FROM permission WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/permission/<int:pid>", methods=["PUT"])
def update_permission(pid):
    data = json_body()
    _validate_permission(data)
    allowed = ["code", "name", "resource", "action", "description"]
    fields = [f for f in allowed if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [pid]
    conn = get_db()
    try:
        cur = conn.execute(f"UPDATE permission SET {sets} WHERE id=?", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ code аль хэдийн бүртгэгдсэн байна")
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Эрх олдсонгүй")
    return jsonify(updated=pid, fields=fields)


@bp.route("/api/permission/<int:pid>", methods=["DELETE"])
def delete_permission(pid):
    conn = get_db()
    cur = conn.execute("DELETE FROM permission WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Эрх олдсонгүй")
    return jsonify(deleted=pid)


# ======================= role (Дүр) =======================
@bp.route("/api/role", methods=["GET"])
def list_role():
    conn = get_db()
    data = rows(conn.execute("SELECT * FROM role ORDER BY id").fetchall())
    for r in data:
        r["permissions"] = _role_perms(conn, r["id"])
    conn.close()
    return jsonify(data)


@bp.route("/api/role/<int:rid>", methods=["GET"])
def get_role(rid):
    conn = get_db()
    row = conn.execute("SELECT * FROM role WHERE id=?", (rid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Дүр олдсонгүй")
    out = dict(row)
    out["permissions"] = _role_perms(conn, rid)
    out["user_count"] = conn.execute(
        "SELECT COUNT(*) FROM app_user WHERE role_id=?", (rid,)).fetchone()[0]
    conn.close()
    return jsonify(out)


@bp.route("/api/role", methods=["POST"])
def create_role():
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO role(name, description) VALUES (?, ?)",
                           (data["name"], data.get("description")))
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ дүрийн нэр аль хэдийн бүртгэгдсэн байна")
    rid = cur.lastrowid
    if isinstance(data.get("permission_ids"), list):
        _set_role_permissions(conn, rid, data["permission_ids"])
        conn.commit()
    out = dict(conn.execute("SELECT * FROM role WHERE id=?", (rid,)).fetchone())
    out["permissions"] = _role_perms(conn, rid)
    conn.close()
    return jsonify(out), 201


@bp.route("/api/role/<int:rid>", methods=["PUT"])
def update_role(rid):
    data = json_body()
    conn = get_db()
    if not conn.execute("SELECT 1 FROM role WHERE id=?", (rid,)).fetchone():
        conn.close()
        abort(404, description="Дүр олдсонгүй")
    fields = [f for f in ("name", "description") if f in data]
    if fields:
        sets = ", ".join(f"{f}=?" for f in fields)
        vals = [data[f] for f in fields] + [rid]
        try:
            conn.execute(f"UPDATE role SET {sets} WHERE id=?", vals)
        except Exception:
            conn.close()
            abort(409, description="Энэ дүрийн нэр аль хэдийн бүртгэгдсэн байна")
    # permission_ids өгвөл эрхийн жагсаалтыг бүхэлд нь солино
    if isinstance(data.get("permission_ids"), list):
        _set_role_permissions(conn, rid, data["permission_ids"])
    conn.commit()
    out = dict(conn.execute("SELECT * FROM role WHERE id=?", (rid,)).fetchone())
    out["permissions"] = _role_perms(conn, rid)
    conn.close()
    return jsonify(out)


@bp.route("/api/role/<int:rid>", methods=["DELETE"])
def delete_role(rid):
    conn = get_db()
    cur = conn.execute("DELETE FROM role WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Дүр олдсонгүй")
    return jsonify(deleted=rid)


# ---- Дүрд эрх нэг нэгээр нэмэх / хасах ----
@bp.route("/api/role/<int:rid>/permission", methods=["POST"])
def add_role_permission(rid):
    data = request.get_json(silent=True)
    require(data, ["permission_id"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM role WHERE id=?", (rid,)).fetchone():
        conn.close()
        abort(404, description="Дүр олдсонгүй")
    pid = data["permission_id"]
    if not conn.execute("SELECT 1 FROM permission WHERE id=?", (pid,)).fetchone():
        conn.close()
        abort(400, description="permission_id олдсонгүй")
    conn.execute(
        "INSERT OR IGNORE INTO role_permission(role_id, permission_id) VALUES (?, ?)",
        (rid, pid))
    conn.commit()
    out = _role_perms(conn, rid)
    conn.close()
    return jsonify(role_id=rid, permissions=out), 201


@bp.route("/api/role/<int:rid>/permission/<int:pid>", methods=["DELETE"])
def remove_role_permission(rid, pid):
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM role_permission WHERE role_id=? AND permission_id=?", (rid, pid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Тухайн дүрд энэ эрх байхгүй байна")
    return jsonify(role_id=rid, removed_permission=pid)


# ======================= app_user (Хэрэглэгч) =======================
def _check_role(conn, data):
    """role_id өгсөн (null биш) бол дүр байгаа эсэхийг шалгана."""
    rid = data.get("role_id")
    if rid is None:
        return
    if not conn.execute("SELECT 1 FROM role WHERE id=?", (rid,)).fetchone():
        conn.close()
        abort(400, description="role_id (дүр) олдсонгүй")


@bp.route("/api/user", methods=["GET"])
def list_user():
    role_id = request.args.get("role_id")
    conn = get_db()
    sql = ("SELECT u.*, r.name AS role_name "
           "FROM app_user u LEFT JOIN role r ON r.id = u.role_id")
    params = []
    if role_id:
        sql += " WHERE u.role_id=?"
        params.append(role_id)
    sql += " ORDER BY u.id"
    data = [public_user(x) for x in conn.execute(sql, params).fetchall()]
    conn.close()
    return jsonify(data)


@bp.route("/api/user/<int:uid>", methods=["GET"])
def get_user(uid):
    conn = get_db()
    row = conn.execute(
        "SELECT u.*, r.name AS role_name "
        "FROM app_user u LEFT JOIN role r ON r.id = u.role_id WHERE u.id=?",
        (uid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    out = public_user(row)
    # Дүрээс удамшсан бодит эрхүүд
    out["permissions"] = _role_perms(conn, row["role_id"]) if row["role_id"] else []
    conn.close()
    return jsonify(out)


@bp.route("/api/user", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    conn = get_db()
    _check_role(conn, data)
    try:
        cur = conn.execute(
            "INSERT INTO app_user(username, password_hash, full_name, email, "
            "role_id, is_active) VALUES (?,?,?,?,?,?)",
            (data["username"], generate_password_hash(data["password"], method="pbkdf2"),
             data.get("full_name"), data.get("email"),
             data.get("role_id"),
             1 if data.get("is_active", 1) else 0))
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ нэвтрэх нэр аль хэдийн бүртгэгдсэн байна")
    row = conn.execute("SELECT * FROM app_user WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(public_user(row)), 201


@bp.route("/api/user/<int:uid>", methods=["PUT"])
def update_user(uid):
    data = json_body()
    conn = get_db()
    _check_role(conn, data)
    cols, vals = [], []
    for f in USER_FIELDS:  # full_name, email, role_id, is_active — дүрээ сонгох нь энд
        if f in data:
            cols.append(f)
            # is_active-г л 0/1 болгоно; бусад талбарыг хэвээр нь дамжуулна
            vals.append((1 if data[f] else 0) if f == "is_active" else data[f])
    if data.get("password"):  # шинэ нууц үг өгвөл дахин hash хийнэ
        cols.append("password_hash")
        vals.append(generate_password_hash(data["password"], method="pbkdf2"))
    if not cols:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{c}=?" for c in cols)
    cur = conn.execute(f"UPDATE app_user SET {sets} WHERE id=?", vals + [uid])
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    row = conn.execute("SELECT * FROM app_user WHERE id=?", (uid,)).fetchone()
    conn.close()
    return jsonify(public_user(row))


@bp.route("/api/user/<int:uid>", methods=["DELETE"])
def delete_user(uid):
    conn = get_db()
    cur = conn.execute("DELETE FROM app_user WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Хэрэглэгч олдсонгүй")
    return jsonify(deleted=uid)


# ---- Нэвтрэлт шалгах (нууц үг зөв эсэхийг шалгах туслах endpoint) ----
@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    conn = get_db()
    row = conn.execute(
        "SELECT u.*, r.name AS role_name "
        "FROM app_user u LEFT JOIN role r ON r.id = u.role_id WHERE u.username=?",
        (data["username"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], data["password"]):
        conn.close()
        abort(400, description="Нэвтрэх нэр эсвэл нууц үг буруу")
    if not row["is_active"]:
        conn.close()
        abort(400, description="Хэрэглэгчийн эрх идэвхгүй байна")
    out = public_user(row)
    out["permissions"] = _role_perms(conn, row["role_id"]) if row["role_id"] else []
    conn.close()
    return jsonify(out)
