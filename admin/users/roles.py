"""role (Дүр) — CRUD ба дүрд эрх нэмэх / хасах."""
from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import rows, require, json_body, fail, insert_row, update_row, fetch_page, list_json

from admin.users import bp
from admin.users.common import _delete_by_id, _exists, _role_perms


def _role_out(conn, rid):
    """Дүрийн мөр + эрхүүд."""
    out = dict(conn.execute("SELECT * FROM role WHERE id=?", (rid,)).fetchone())
    out["permissions"] = _role_perms(conn, rid)
    return out


def _set_role_permissions(conn, rid, permission_ids):
    """Дүрийн эрхийн жагсаалтыг бүхэлд нь солино (хуучныг устгаад шинээр оноох).

    Бүх id лавлахад байх ёстой (үгүй бол 400).
    """
    ids = list(dict.fromkeys(permission_ids))  # давхардлыг арилгана, дараалал хадгална
    if ids:
        found = conn.execute(
            f"SELECT COUNT(*) FROM permission WHERE id IN ({', '.join('?' * len(ids))})",
            ids).fetchone()[0]
        if found != len(ids):
            fail(conn, 400, "Зарим permission_id олдсонгүй")
    conn.execute("DELETE FROM role_permission WHERE role_id=?", (rid,))
    conn.executemany(
        "INSERT OR IGNORE INTO role_permission(role_id, permission_id) VALUES (?, ?)",
        [(rid, pid) for pid in ids])


# ======================= role (Дүр) =======================
ROLE_DUP = "Энэ дүрийн нэр аль хэдийн бүртгэгдсэн байна"
ROLE_FIELDS = ("name", "code", "description")


def _role_values(conn, data, rid=None):
    """Ирсэн талбаруудаас хадгалах утгыг бэлтгэнэ; `code`-г шалгана.

    code нь заавал биш: хоосон мөр -> NULL. Хуучин DB-д багана ALTER-ээр нэмэгдсэн тул
    DB-д UNIQUE байхгүй — давхцлыг энд шалгана (409).
    """
    values = {f: data[f] for f in ROLE_FIELDS if f in data}
    if "code" in values:
        code = values["code"]
        if code is not None and not isinstance(code, str):
            fail(conn, 400, "code нь текст байх ёстой")
        code = (code or "").strip() or None
        if code is not None and conn.execute(
                "SELECT 1 FROM role WHERE code=? AND id<>?", (code, rid or 0)).fetchone():
            fail(conn, 409, f"'{code}' кодтой дүр аль хэдийн бүртгэгдсэн байна")
        values["code"] = code
    return values


@bp.route("/api/role", methods=["GET"])
def list_role():
    conn = get_db()
    page_rows, meta = fetch_page(conn, "SELECT * FROM role ORDER BY id")
    data = rows(page_rows)
    for r in data:
        r["permissions"] = _role_perms(conn, r["id"])
    conn.close()
    return list_json(data, meta)


@bp.route("/api/role/<int:rid>", methods=["GET"])
def get_role(rid):
    conn = get_db()
    if not _exists(conn, "role", rid):
        fail(conn, 404, "Дүр олдсонгүй")
    out = _role_out(conn, rid)
    out["user_count"] = conn.execute(
        "SELECT COUNT(*) FROM app_user WHERE role_id=?", (rid,)).fetchone()[0]
    conn.close()
    return jsonify(out)


@bp.route("/api/role", methods=["POST"])
def create_role():
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    values = _role_values(conn, data)
    try:
        rid = insert_row(conn, "role", values)
        conn.commit()
    except Exception:
        fail(conn, 409, ROLE_DUP)
    if isinstance(data.get("permission_ids"), list):
        _set_role_permissions(conn, rid, data["permission_ids"])
        conn.commit()
    out = _role_out(conn, rid)
    conn.close()
    return jsonify(out), 201


@bp.route("/api/role/<int:rid>", methods=["PUT", "PATCH"])
def update_role(rid):
    data = json_body()
    conn = get_db()
    if not _exists(conn, "role", rid):
        fail(conn, 404, "Дүр олдсонгүй")
    values = _role_values(conn, data, rid)
    if values:
        try:
            update_row(conn, "role", rid, values)
        except Exception:
            fail(conn, 409, ROLE_DUP)
    # permission_ids өгвөл эрхийн жагсаалтыг бүхэлд нь солино
    if isinstance(data.get("permission_ids"), list):
        _set_role_permissions(conn, rid, data["permission_ids"])
    conn.commit()
    out = _role_out(conn, rid)
    conn.close()
    return jsonify(out)


@bp.route("/api/role/<int:rid>", methods=["DELETE"])
def delete_role(rid):
    return _delete_by_id("role", rid, "Дүр олдсонгүй")


# ---- Дүрд эрх нэг нэгээр нэмэх / хасах ----
@bp.route("/api/role/<int:rid>/permission", methods=["POST"])
def add_role_permission(rid):
    data = request.get_json(silent=True)
    require(data, ["permission_id"])
    conn = get_db()
    if not _exists(conn, "role", rid):
        fail(conn, 404, "Дүр олдсонгүй")
    pid = data["permission_id"]
    if not _exists(conn, "permission", pid):
        fail(conn, 400, "permission_id олдсонгүй")
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
