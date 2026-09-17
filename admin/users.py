"""Хэрэглэгчийн удирдлагын CRUD (Blueprint).

Бүтэц:
  permission (Эрх)  — CRUD үйлдэл бүр нэг эрх (ж: 'user.create')
  role (Дүр)        — role_permission-оор дамжуулан ОЛОН эрхтэй (M:N)
  app_user (Хэрэглэгч) — role_id-аар нэг дүр СОНГОЖ, дүрийнхээ бүх эрхийг удамшуулна
  user_scope (Хамрах хүрээ) — тухайн хэрэглэгч АЛЬ өгөгдлийг харахыг заана (1:1)

Мөн "өөрийн" (self-service) маршрутууд — /api/change_password, /api/me/...
(specialist_onboarding_api_spec.md): анх нэвтрэхэд нууц үг солих, дараа нь
хамрах хүрээгээ баталгаажуулж onboarding-оо дуусгах. Эдгээр нь ҮРГЭЛЖ g.user
дээр ажиллах тул auth.py тусгай эрх шаардахгүй (SELF_PATHS / SELF_PREFIXES).
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, abort, g
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db
from helpers import rows, require, json_body
from auth import make_token
from scope_core import (RURAL, SCHOOL_TYPE_CATEGORY, is_specialist,
                        public_scope, load_scope, org_condition)

bp = Blueprint("users", __name__)

ACTIONS = ("create", "read", "update", "delete")

# --- Хамрах хүрээ (user_scope, user_scope_api_spec.md) ---
# Сургуулийн төрлийн тогтвортой кодууд (бүтэн нэрийг frontend харуулна).
# rural-аас бусад бүр нь ангиллын id-тай харгалзах ёстой тул жагсаалтыг
# scope_core.SCHOOL_TYPE_CATEGORY-ЭЭС гаргана — зөрөх (шүүлт хоосон буцаах)
# боломжгүй болно.
SCHOOL_TYPES = tuple(SCHOOL_TYPE_CATEGORY) + (RURAL,)
# "ХОН" (RURAL) — зөвхөн энэ төрөлд тодорхой сургуулиудыг (organization_ids) сонгоно,
# бусад төрөлд ганц дүүрэг (district_au2_code) сонгоно.
SCOPE_FIELDS = ("school_type", "district_au2_code", "organization_ids", "organization_id")
EMPTY_SCOPE = {"school_type": None, "district_au2_code": None,
               "organization_ids": [], "organization_id": None}

# Хэрэглэгчийн засаж/оруулж болох талбарууд (password, username-ээс бусад тусад нь).
# Нэр нь овог/нэр гэж ТУСДАА хадгалагдана (member-тэй ижил зарчим).
# `must_change_password`-ыг админ дахин 1 болгож, нууц үг сэргээсний дараа
# хэрэглэгчээс дахин солиулж болно.
USER_FIELDS = ("last_name", "first_name", "email", "role_id", "structure_id", "is_active",
               "must_change_password")
# DB-д 0/1 болж хадгалагдах логик талбарууд
BOOL_FIELDS = ("is_active", "must_change_password")

# Хэрэглэгчийг дүр ба бүтцийн удирдлагынх нь нэртэй хамт унших SELECT
USER_SELECT = (
    "SELECT u.*, r.name AS role_name, st.name AS structure_name, st.code AS structure_code "
    "FROM app_user u "
    "LEFT JOIN role r ON r.id = u.role_id "
    "LEFT JOIN structure st ON st.id = u.structure_id"
)


# ----------------------------- Туслахууд -----------------------------
def public_user(row):
    """Хэрэглэгчийн мөрөөс password_hash-г хасаад буцаана.

    Нэр нь last_name (Овог) + first_name (Нэр) гэж ТУСАД нь хадгалагдана —
    `full_name` гэсэн талбар байхгүй (хадгалахгүй, буцаахгүй).

    Анхны нэвтрэлтийн 2 талбарыг frontend-д тохиромжтой boolean-оор буцаана
    (specialist_onboarding_api_spec.md §3.1). `onboarding_completed` нь зөвхөн
    Зөвлөх мэргэжилтэнд утга учиртай — бусад дүрд onboarding алхам байхгүй тул
    ҮРГЭЛЖ true (шууд Dashboard руу).
    """
    d = dict(row)
    d.pop("password_hash", None)
    d["must_change_password"] = bool(d.get("must_change_password"))
    d["onboarding_completed"] = (
        bool(d.get("onboarding_completed_at")) if is_specialist(row) else True)
    return d


def _require_user(conn, uid):
    if not conn.execute("SELECT 1 FROM app_user WHERE id=?", (uid,)).fetchone():
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")


def _validate_scope(conn, s):
    """Хамрах хүрээний бизнес дүрмүүд (user_scope_api_spec.md §6). Зөрвөл 400."""
    def bad(msg):
        conn.close()
        abort(400, description=msg)

    st = s["school_type"]
    if st is not None and st not in SCHOOL_TYPES:
        bad("school_type буруу байна: " + ", ".join(SCHOOL_TYPES))

    ids = s["organization_ids"]
    if ids is None:
        ids = s["organization_ids"] = []
    if not isinstance(ids, list):
        bad("organization_ids нь массив байх ёстой")
    try:
        ids = s["organization_ids"] = [int(x) for x in ids]
    except (TypeError, ValueError):
        bad("organization_ids нь бүхэл тооны массив байх ёстой")

    if st == RURAL:
        if s["district_au2_code"]:
            bad("school_type='rural' үед district_au2_code сонгохгүй "
                "(тодорхой сургуулиудыг organization_ids-ээр сонгоно)")
    elif st is not None:
        if not s["district_au2_code"]:
            bad(f"school_type='{st}' үед district_au2_code заавал")
        if ids:
            bad(f"school_type='{st}' үед organization_ids хоосон байх ёстой")

    if s["district_au2_code"] and not conn.execute(
            "SELECT 1 FROM admin_unit2 WHERE au2_code=?", (s["district_au2_code"],)).fetchone():
        bad("district_au2_code (дүүрэг) олдсонгүй")

    for oid in ids:
        if not conn.execute("SELECT 1 FROM organization WHERE id=?", (oid,)).fetchone():
            bad(f"organization_ids: {oid} дугаартай байгууллага олдсонгүй")

    if s["organization_id"] is not None and not conn.execute(
            "SELECT 1 FROM organization WHERE id=?", (s["organization_id"],)).fetchone():
        bad("organization_id (сургууль) олдсонгүй")


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


@bp.route("/api/permission/<int:pid>", methods=["PUT", "PATCH"])
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


@bp.route("/api/role/<int:rid>", methods=["PUT", "PATCH"])
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


def _check_structure(conn, data):
    """structure_id өгсөн (null биш) бол лавлахад байгаа эсэхийг шалгана."""
    sid = data.get("structure_id")
    if sid is None:
        return
    if not conn.execute("SELECT 1 FROM structure WHERE id=?", (sid,)).fetchone():
        conn.close()
        abort(400, description="structure_id (бүтцийн удирдлага) олдсонгүй")


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
    data = [public_user(x) for x in conn.execute(sql, params).fetchall()]
    # Хамрах хүрээг шууд хамт өгнө — хэрэглэгч бүрээр /scope дуудах шаардлагагүй
    scopes = {r["user_id"]: public_scope(r)
              for r in conn.execute("SELECT * FROM user_scope").fetchall()}
    for u in data:
        u["scope"] = scopes.get(u["id"])
    conn.close()
    return jsonify(data)


@bp.route("/api/user/<int:uid>", methods=["GET"])
def get_user(uid):
    conn = get_db()
    row = conn.execute(USER_SELECT + " WHERE u.id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    out = public_user(row)
    # Дүрээс удамшсан бодит эрхүүд
    out["permissions"] = _role_perms(conn, row["role_id"]) if row["role_id"] else []
    out["scope"] = load_scope(conn, uid)
    conn.close()
    return jsonify(out)


@bp.route("/api/user", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    conn = get_db()
    _check_role(conn, data)
    _check_structure(conn, data)
    try:
        cur = conn.execute(
            "INSERT INTO app_user(username, password_hash, last_name, first_name, "
            "email, role_id, structure_id, is_active, must_change_password) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (data["username"], generate_password_hash(data["password"], method="pbkdf2"),
             data.get("last_name"), data.get("first_name"), data.get("email"),
             data.get("role_id"), data.get("structure_id"),
             1 if data.get("is_active", 1) else 0,
             # Админ өгсөн анхны нууц үг (ихэвчлэн утасны дугаар) — хэрэглэгч
             # анх нэвтрэхэд ЗААВАЛ солино (спек §2). Хүсвэл 0-ээр дарж болно.
             1 if data.get("must_change_password", 1) else 0))
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ нэвтрэх нэр аль хэдийн бүртгэгдсэн байна")
    row = conn.execute(USER_SELECT + " WHERE u.id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(public_user(row)), 201


@bp.route("/api/user/<int:uid>", methods=["PUT", "PATCH"])
def update_user(uid):
    data = json_body()
    conn = get_db()
    _check_role(conn, data)
    _check_structure(conn, data)
    cols, vals = [], []
    for f in USER_FIELDS:  # last_name, first_name, email, role_id, is_active ...
        if f in data:
            cols.append(f)
            # Логик талбаруудыг л 0/1 болгоно; бусдыг хэвээр нь дамжуулна
            vals.append((1 if data[f] else 0) if f in BOOL_FIELDS else data[f])
    if data.get("password"):  # шинэ нууц үг өгвөл дахин hash хийнэ
        cols.append("password_hash")
        vals.append(generate_password_hash(data["password"], method="pbkdf2"))
    if not cols:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга")
    # Дүр СОЛИГДВОЛ хуучин хамрах хүрээ утгаа алддаг тул цэвэрлэнэ (спек §6)
    if "role_id" in data:
        old = conn.execute("SELECT role_id FROM app_user WHERE id=?", (uid,)).fetchone()
        if old and old["role_id"] != data["role_id"]:
            conn.execute("DELETE FROM user_scope WHERE user_id=?", (uid,))
    sets = ", ".join(f"{c}=?" for c in cols)
    cur = conn.execute(f"UPDATE app_user SET {sets} WHERE id=?", vals + [uid])
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    row = conn.execute(USER_SELECT + " WHERE u.id=?", (uid,)).fetchone()
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


# ============ user_scope (Хамрах хүрээ) — user_scope_api_spec.md ============
# Маршрутын БИЕ нь /api/user/<uid>/scope (админ) ба /api/me/scope (өөрөө)
# хоёрт хуваалцагдана — ялгаа нь зөвхөн АЛЬ хэрэглэгчийн id-г авахад.
def _scope_get(uid):
    conn = get_db()
    _require_user(conn, uid)
    out = load_scope(conn, uid)
    conn.close()
    return jsonify(out)          # мөр байхгүй бол null


def _scope_save(uid):
    """Хамрах хүрээг хадгална (upsert).

    PUT   — БҮХЭЛД нь дарж бичнэ (илгээгээгүй талбар хоосон болно).
    PATCH — зөвхөн илгээсэн талбарыг сольж, бусдыг нь хэвээр үлдээнэ.
    """
    data = json_body()
    conn = get_db()
    _require_user(conn, uid)
    scope = dict(EMPTY_SCOPE)
    if request.method == "PATCH":
        scope.update({k: v for k, v in (load_scope(conn, uid) or {}).items()
                      if k in SCOPE_FIELDS})
    for f in SCOPE_FIELDS:
        if f in data:
            scope[f] = data[f]
    _validate_scope(conn, scope)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO user_scope(user_id, school_type, district_au2_code, "
        "organization_ids, organization_id, updated_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET school_type=excluded.school_type, "
        "district_au2_code=excluded.district_au2_code, "
        "organization_ids=excluded.organization_ids, "
        "organization_id=excluded.organization_id, updated_at=excluded.updated_at",
        (uid, scope["school_type"], scope["district_au2_code"],
         json.dumps(scope["organization_ids"]), scope["organization_id"], now))
    conn.commit()
    out = load_scope(conn, uid)
    conn.close()
    return jsonify(out)


def _scope_delete(uid):
    conn = get_db()
    _require_user(conn, uid)
    cur = conn.execute("DELETE FROM user_scope WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Хамрах хүрээ бүртгэгдээгүй байна")
    return jsonify(deleted=uid)


@bp.route("/api/user/<int:uid>/scope", methods=["GET"])
def get_user_scope(uid):
    return _scope_get(uid)


@bp.route("/api/user/<int:uid>/scope", methods=["PUT", "PATCH"])
def save_user_scope(uid):
    return _scope_save(uid)


@bp.route("/api/user/<int:uid>/scope", methods=["DELETE"])
def delete_user_scope(uid):
    return _scope_delete(uid)


# ---- Нэвтрэлт (нээлттэй) — амжилттай бол Bearer токен буцаана ----
@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    conn = get_db()
    row = conn.execute(USER_SELECT + " WHERE u.username=?", (data["username"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], data["password"]):
        conn.close()
        abort(400, description="Нэвтрэх нэр эсвэл нууц үг буруу")
    if not row["is_active"]:
        conn.close()
        abort(400, description="Хэрэглэгчийн эрх идэвхгүй байна")
    out = public_user(row)
    out["permissions"] = _role_perms(conn, row["role_id"]) if row["role_id"] else []
    out["scope"] = load_scope(conn, row["id"])
    conn.close()
    # Дараагийн хүсэлтүүдэд ашиглах токен: Authorization: Bearer <token>
    out["token"] = make_token(row["id"])
    return jsonify(out)


# ==== Өөрийн эрхээр (self-service) — specialist_onboarding_api_spec.md §3-§4 ====
# auth.py эдгээрт токен шаардана ч ТУСГАЙ ЭРХ шаардахгүй (SELF_PATHS /
# SELF_PREFIXES) — хэрэглэгч зөвхөн ӨӨРИЙН өгөгдөлд хүрнэ.
def _me_id():
    """Токен эзэмшигчийн id (before_request нь g.user-ыг ачаалсан байх ёстой)."""
    user = getattr(g, "user", None)
    if user is None:
        abort(401, description="Нэвтрэх шаардлагатай")
    return user["id"]


@bp.route("/api/change_password", methods=["POST"])
def change_password():
    """Нэвтэрсэн хэрэглэгч өөрийн нууц үгээ солино (спек §3.2).

    Амжилттай бол `must_change_password` нь 0 болж, анхны нэвтрэлтийн түгжээ
    тайлагдана. Одоогийн нууц үг буруу бол 422.
    """
    data = json_body()
    require(data, ["current_password", "new_password"])
    uid = _me_id()
    conn = get_db()
    row = conn.execute("SELECT password_hash FROM app_user WHERE id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    if not check_password_hash(row["password_hash"], data["current_password"]):
        conn.close()
        abort(422, description="Одоогийн нууц үг буруу байна")
    conn.execute(
        "UPDATE app_user SET password_hash=?, must_change_password=0 WHERE id=?",
        (generate_password_hash(data["new_password"], method="pbkdf2"), uid))
    conn.commit()
    conn.close()
    return jsonify(status=True)


@bp.route("/api/me", methods=["GET"])
def get_me():
    """Өөрийн профайл — /api/login-тэй ижил хэлбэр (токеноос бусад).

    Нууц үг солих / onboarding-ийн дараа frontend-д төлөвөө дахин уншихад.
    """
    uid = _me_id()
    conn = get_db()
    row = conn.execute(USER_SELECT + " WHERE u.id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    out = public_user(row)
    out["permissions"] = _role_perms(conn, row["role_id"]) if row["role_id"] else []
    out["scope"] = load_scope(conn, uid)
    conn.close()
    return jsonify(out)


@bp.route("/api/me/scope", methods=["GET"])
def get_my_scope():
    """Өөрийн хамрах хүрээ — админ урьдчилан тохируулсан бол бөглөгдөж ирнэ (§4.1)."""
    return _scope_get(_me_id())


@bp.route("/api/me/scope", methods=["PUT", "PATCH"])
def save_my_scope():
    """Өөрийн хамрах хүрээг баталгаажуулах/засах (payload нь /api/user/<id>/scope-той ижил)."""
    return _scope_save(_me_id())


@bp.route("/api/me/organizations", methods=["GET"])
def list_my_organizations():
    """Өөрийн хамрах хүрээнд багтах байгууллагууд (§4.2).

    Мэргэжилтэн эндээс дутуу мэдээллийг хараад `PUT /api/organization/<id>`-ээр
    бөглөнө — ямар ч талбар ЗААВАЛ биш, зарим нь хоосон үлдэж болно.
    """
    conn = get_db()
    cond, params = org_condition(conn, alias="o")
    sql = ("SELECT o.id, o.name, o.contact_name, o.phone1, o.phone2, o.email "
           "FROM organization o")
    if cond:
        sql += " WHERE " + cond
    data = rows(conn.execute(sql + " ORDER BY o.id", params).fetchall())
    conn.close()
    return jsonify(items=data)


@bp.route("/api/me/onboarding/complete", methods=["POST"])
def complete_my_onboarding():
    """Onboarding-ийг дууссан гэж тэмдэглэнэ (§4.3).

    Ямар ч талбар бөглөгдсөн байхыг ШАЛГАХГҮЙ — энэ дэлгэцийг дахин
    харуулахгүй гэдгийг л тэмдэглэх зорилготой.
    """
    uid = _me_id()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = get_db()
    cur = conn.execute(
        "UPDATE app_user SET onboarding_completed_at=COALESCE(onboarding_completed_at, ?) "
        "WHERE id=?", (now, uid))
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        abort(404, description="Хэрэглэгч олдсонгүй")
    row = conn.execute(
        "SELECT onboarding_completed_at FROM app_user WHERE id=?", (uid,)).fetchone()
    conn.close()
    return jsonify(status=True, onboarding_completed=True,
                   onboarding_completed_at=row["onboarding_completed_at"])
