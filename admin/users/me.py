"""Нэвтрэлт ба өөрийн эрхээр (self-service) маршрутууд.

/api/login, /api/change_password, /api/me/... (specialist_onboarding_api_spec.md §3-§4).
Тусгай эрх шаардахгүй (core/auth.py-ийн SELF_PATHS / SELF_PREFIXES) — үргэлж
g.user дээр ажиллана.
"""
from flask import jsonify, request, abort, g
from sqlalchemy import func, select, update
from werkzeug.security import check_password_hash

from core import audit
from core.helpers import require, json_body
from core.auth import make_token
from core.orm import session
from core.orm.models import AppUser, Organization
from core.orm.query import paginate
from core.scope_core import org_clause

from admin.users import bp
from admin.users import login_guard
from admin.users.common import _hash, _now, _user_profile, _user_row, needs_rehash
from admin.users.scope import _scope_get, _scope_save


# ---- Нэвтрэлт (нээлттэй) — амжилттай бол Bearer токен буцаана ----
@bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    require(data, ["username", "password"])
    s = session()
    login_guard.check(data["username"])                  # brute-force хязгаар -> 429
    row = _user_row(username=data["username"])
    if not row or not check_password_hash(row["password_hash"], data["password"]):
        login_guard.record_failure(data["username"])
        audit.event("login_failed", username=data["username"], reason="bad_credentials")
        abort(400, description="Нэвтрэх нэр эсвэл нууц үг буруу")
    if not row["is_active"]:
        audit.event("login_failed", username=data["username"], reason="inactive")
        abort(400, description="Хэрэглэгчийн эрх идэвхгүй байна")
    login_guard.reset(data["username"])
    if needs_rehash(row["password_hash"]):                # хуучин 1M давталттай hash -> 600k
        s.execute(update(AppUser).where(AppUser.id == row["id"])
                  .values(password_hash=_hash(data["password"])))
    s.commit()
    audit.event("login", user_id=row["id"], username=row["username"])
    out = _user_profile(row)
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
    s = session()
    user = s.get(AppUser, uid)
    if user is None:
        abort(404, description="Хэрэглэгч олдсонгүй")
    if not check_password_hash(user.password_hash, data["current_password"]):
        abort(422, description="Одоогийн нууц үг буруу байна")
    user.password_hash = _hash(data["new_password"])
    user.must_change_password = 0
    s.commit()
    return jsonify(status=True)


@bp.route("/api/me", methods=["GET"])
def get_me():
    """Өөрийн профайл — /api/login-тэй ижил хэлбэр (токеноос бусад).

    Нууц үг солих / onboarding-ийн дараа frontend-д төлөвөө дахин уншихад.
    """
    row = _user_row(_me_id())
    if not row:
        abort(404, description="Хэрэглэгч олдсонгүй")
    return jsonify(_user_profile(row))


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
    stmt = select(Organization.id, Organization.name, Organization.contact_name,
                  Organization.phone1, Organization.phone2, Organization.email)
    cond = org_clause()
    if cond is not None:
        stmt = stmt.where(cond)
    data, meta = paginate(stmt.order_by(Organization.id), mappings=True)
    return jsonify(items=[dict(r) for r in data], **(meta or {}))


@bp.route("/api/me/onboarding/complete", methods=["POST"])
def complete_my_onboarding():
    """Onboarding-ийг дууссан гэж тэмдэглэнэ (§4.3).

    Ямар ч талбар бөглөгдсөн байхыг ШАЛГАХГҮЙ — энэ дэлгэцийг дахин
    харуулахгүй гэдгийг л тэмдэглэх зорилготой.
    """
    uid = _me_id()
    s = session()
    count = s.execute(update(AppUser).where(AppUser.id == uid).values(
        onboarding_completed_at=func.coalesce(AppUser.onboarding_completed_at, _now()))).rowcount
    s.commit()
    if count == 0:
        abort(404, description="Хэрэглэгч олдсонгүй")
    done = s.scalar(select(AppUser.onboarding_completed_at).where(AppUser.id == uid))
    return jsonify(status=True, onboarding_completed=True, onboarding_completed_at=done)
