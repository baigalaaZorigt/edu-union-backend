"""Нэвтрэлт ба өөрийн эрхээр (self-service) маршрутууд.

/api/login, /api/change_password, /api/me/... (specialist_onboarding_api_spec.md §3-§4).
Тусгай эрх шаардахгүй (core/auth.py-ийн SELF_PATHS / SELF_PREFIXES) — үргэлж
g.user дээр ажиллана.
"""
from flask import jsonify, request, abort, g
from werkzeug.security import check_password_hash

from core import audit
from core.db import get_db
from core.helpers import rows, require, json_body, fail, update_row, fetch_page
from core.auth import make_token
from core.scope_core import org_condition

from admin.users import bp
from admin.users import login_guard
from admin.users.common import USER_SELECT, _hash, _now, _user_profile, _user_row, needs_rehash
from admin.users.scope import _scope_get, _scope_save


# ---- Нэвтрэлт (нээлттэй) — амжилттай бол Bearer токен буцаана ----
@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    conn = get_db()
    login_guard.check(conn, data["username"])            # brute-force хязгаар -> 429
    row = conn.execute(USER_SELECT + " WHERE u.username=?", (data["username"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], data["password"]):
        login_guard.record_failure(conn, data["username"])
        audit.event("login_failed", username=data["username"], reason="bad_credentials")
        fail(conn, 400, "Нэвтрэх нэр эсвэл нууц үг буруу")
    if not row["is_active"]:
        audit.event("login_failed", username=data["username"], reason="inactive")
        fail(conn, 400, "Хэрэглэгчийн эрх идэвхгүй байна")
    login_guard.reset(conn, data["username"])
    if needs_rehash(row["password_hash"]):                # хуучин 1M давталттай hash -> 600k
        update_row(conn, "app_user", row["id"], {"password_hash": _hash(data["password"])})
    conn.commit()
    audit.event("login", user_id=row["id"], username=row["username"])
    out = _user_profile(conn, row)
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
        fail(conn, 404, "Хэрэглэгч олдсонгүй")
    if not check_password_hash(row["password_hash"], data["current_password"]):
        fail(conn, 422, "Одоогийн нууц үг буруу байна")
    update_row(conn, "app_user", uid,
               {"password_hash": _hash(data["new_password"]), "must_change_password": 0})
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
    row = _user_row(conn, uid)
    if not row:
        fail(conn, 404, "Хэрэглэгч олдсонгүй")
    out = _user_profile(conn, row)
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
    data, meta = fetch_page(conn, sql + " ORDER BY o.id", params)
    conn.close()
    return jsonify(items=rows(data), **(meta or {}))


@bp.route("/api/me/onboarding/complete", methods=["POST"])
def complete_my_onboarding():
    """Onboarding-ийг дууссан гэж тэмдэглэнэ (§4.3).

    Ямар ч талбар бөглөгдсөн байхыг ШАЛГАХГҮЙ — энэ дэлгэцийг дахин
    харуулахгүй гэдгийг л тэмдэглэх зорилготой.
    """
    uid = _me_id()
    conn = get_db()
    cur = conn.execute(
        "UPDATE app_user SET onboarding_completed_at=COALESCE(onboarding_completed_at, ?) "
        "WHERE id=?", (_now(), uid))
    conn.commit()
    if cur.rowcount == 0:
        fail(conn, 404, "Хэрэглэгч олдсонгүй")
    row = conn.execute(
        "SELECT onboarding_completed_at FROM app_user WHERE id=?", (uid,)).fetchone()
    conn.close()
    return jsonify(status=True, onboarding_completed=True,
                   onboarding_completed_at=row["onboarding_completed_at"])
