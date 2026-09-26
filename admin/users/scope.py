"""user_scope (Хамрах хүрээ) — /api/user/<id>/scope (user_scope_api_spec.md)."""
import json

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import json_body, fail
from core.scope_core import RURAL, load_scope

from admin.users import bp
from admin.users.common import SCHOOL_TYPES, _exists, _now


# "ХОН" (RURAL) — зөвхөн энэ төрөлд тодорхой сургуулиудыг (organization_ids) сонгоно,
# бусад төрөлд ганц дүүрэг (district_au2_code) сонгоно.
SCOPE_FIELDS = ("school_type", "district_au2_code", "organization_ids", "organization_id")
EMPTY_SCOPE = {"school_type": None, "district_au2_code": None,
               "organization_ids": [], "organization_id": None}


def _require_user(conn, uid):
    if not _exists(conn, "app_user", uid):
        fail(conn, 404, "Хэрэглэгч олдсонгүй")


def _validate_scope(conn, s):
    """Хамрах хүрээний бизнес дүрмүүд (user_scope_api_spec.md §6). Зөрвөл 400."""
    def bad(msg):
        fail(conn, 400, msg)

    st = s["school_type"]
    if st is not None and st not in SCHOOL_TYPES:
        bad("school_type буруу байна: " + ", ".join(SCHOOL_TYPES))

    ids = s["organization_ids"]
    if ids is None:
        ids = []
    if not isinstance(ids, list):
        bad("organization_ids нь массив байх ёстой")
    try:
        ids = s["organization_ids"] = [int(x) for x in ids]
    except (TypeError, ValueError):
        bad("organization_ids нь бүхэл тооны массив байх ёстой")

    district = s["district_au2_code"]
    if st == RURAL:
        if district:
            bad("school_type='rural' үед district_au2_code сонгохгүй "
                "(тодорхой сургуулиудыг organization_ids-ээр сонгоно)")
    elif st is not None:
        if not district:
            bad(f"school_type='{st}' үед district_au2_code заавал")
        if ids:
            bad(f"school_type='{st}' үед organization_ids хоосон байх ёстой")

    if district and not conn.execute(
            "SELECT 1 FROM admin_unit2 WHERE au2_code=?", (district,)).fetchone():
        bad("district_au2_code (дүүрэг) олдсонгүй")

    for oid in ids:
        if not _exists(conn, "organization", oid):
            bad(f"organization_ids: {oid} дугаартай байгууллага олдсонгүй")

    if s["organization_id"] is not None and not _exists(conn, "organization", s["organization_id"]):
        bad("organization_id (сургууль) олдсонгүй")


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
    scope.update({f: data[f] for f in SCOPE_FIELDS if f in data})
    _validate_scope(conn, scope)
    conn.execute(
        "INSERT INTO user_scope(user_id, school_type, district_au2_code, "
        "organization_ids, organization_id, updated_at) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET school_type=excluded.school_type, "
        "district_au2_code=excluded.district_au2_code, "
        "organization_ids=excluded.organization_ids, "
        "organization_id=excluded.organization_id, updated_at=excluded.updated_at",
        (uid, scope["school_type"], scope["district_au2_code"],
         json.dumps(scope["organization_ids"]), scope["organization_id"], _now()))
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
