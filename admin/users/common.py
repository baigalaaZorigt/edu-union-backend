"""Хэрэглэгчийн модулиудын хуваалцсан тогтмол, query ба туслах функцууд."""
from datetime import datetime, timezone

from flask import abort, g, jsonify
from sqlalchemy import delete, select
from werkzeug.security import generate_password_hash

from core.orm import session
from core.orm.models import AppUser, Permission, Role, RolePermission, Structure, UserScope
from core.scope_core import RURAL, SCHOOL_TYPE_CATEGORY, is_specialist, public_scope


# --- Хамрах хүрээ (user_scope, user_scope_api_spec.md) ---
# Сургуулийн төрлийн тогтвортой кодууд (бүтэн нэрийг frontend харуулна).
# rural-аас бусад бүр нь ангиллын id-тай харгалзах ёстой тул жагсаалтыг
# scope_core.SCHOOL_TYPE_CATEGORY-ЭЭС гаргана — зөрөх (шүүлт хоосон буцаах)
# боломжгүй болно.
SCHOOL_TYPES = tuple(SCHOOL_TYPE_CATEGORY) + (RURAL,)

def user_select():
    """Хэрэглэгч + дүр ба бүтцийн удирдлагын нэр/код (хуучин USER_SELECT-ийн ORM хувилбар).

    Үр дүнг `.mappings()`-аар уншина — багана бүр нэрээрээ (u.* + role_name ...).
    """
    return (select(*AppUser.__table__.c,
                   Role.name.label("role_name"), Role.code.label("role_code"),
                   Structure.name.label("structure_name"), Structure.code.label("structure_code"))
            .select_from(AppUser)             # ORM entity — soft delete шүүлт үйлчилнэ
            .outerjoin(Role, Role.id == AppUser.role_id)
            .outerjoin(Structure, Structure.id == AppUser.structure_id))


# ----------------------------- Туслахууд -----------------------------
def _now():
    """UTC цаг ISO хэлбэрээр (секундийн нарийвчлалтай)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# pbkdf2 (scrypt энэ Python build-д алга). OWASP-ийн PBKDF2-SHA256 зөвлөмж 600k давталт —
# werkzeug-ийн анхдагч 1M нь t3.micro дээр нэвтрэлт бүрт ~0.7 сек CPU иддэг байв.
# Хуучин (өөр тохиргоотой) hash-ийг амжилттай нэвтрэх үед шинэчилнэ (needs_rehash).
HASH_METHOD = "pbkdf2:sha256:600000"


def _hash(password):
    return generate_password_hash(password, method=HASH_METHOD)


def needs_rehash(password_hash):
    return (password_hash or "").split("$", 1)[0] != HASH_METHOD


def _exists(model, key):
    return session().get(model, key) is not None


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
    d.pop("token_version", None)          # дотоод (core/auth.py)
    d["must_change_password"] = bool(d.get("must_change_password"))
    d["onboarding_completed"] = (
        bool(d.get("onboarding_completed_at")) if is_specialist(row) else True)
    return d


def _user_row(uid=None, username=None):
    """Хэрэглэгчийн мөр (dict шиг RowMapping) id эсвэл username-аар; байхгүй бол None."""
    cond = AppUser.id == uid if username is None else AppUser.username == username
    return session().execute(user_select().where(cond)).mappings().first()


# Бүх хэрэглэгчийг харж/засаж/нууц үгийг нь сэргээж чадах дүр: role.code = "1" (Super Admin)
# эсвэл seed-ийн бүх эрхтэй `admin` дүр (кодгүй). Бусад нь зөвхөн ӨӨРИЙН ҮҮСГЭСЭН
# (app_user.created_by) хэрэглэгчдээ харна.
SUPER_ROLE_CODE, SUPER_ROLE_NAME = "1", "admin"


def is_super(user_id=None):
    row = _user_row(g.user["id"] if user_id is None else user_id)
    return bool(row) and (str(row["role_code"] or "").strip() == SUPER_ROLE_CODE
                          or row["role_name"] == SUPER_ROLE_NAME)


def created_by_me():
    """Хэрэглэгчийн жагсаалтад тавих нөхцөл; Super Admin бол None (шүүлтгүй)."""
    return None if is_super() else AppUser.created_by == g.user["id"]


def check_user_access(uid):
    """Super Admin биш бол зөвхөн өөрийн үүсгэсэн хэрэглэгч рүү хандана -> бусад нь 403.
    Байхгүй хэрэглэгчийг шүүхгүй — 404-ийг маршрут өөрөө өгнө."""
    user = session().get(AppUser, uid)
    if user is not None and user.created_by != g.user["id"] and not is_super():
        abort(403, description="Энэ хэрэглэгчийг та бүртгээгүй — зөвхөн бүртгэсэн хүн эсвэл "
                               "Super Admin хандана")


def load_scope(uid):
    """Тухайн хэрэглэгчийн хамрах хүрээ (мөр байхгүй бол None)."""
    row = session().get(UserScope, uid)
    return public_scope(row.to_dict()) if row is not None else None


def _user_profile(row):
    """public_user + дүрээс удамшсан бодит эрхүүд + хамрах хүрээ
    (GET /api/user/<id>, /api/login, /api/me гурав ижил хэлбэртэй)."""
    out = public_user(row)
    out["permissions"] = _role_perms(row["role_id"]) if row["role_id"] else []
    out["scope"] = load_scope(row["id"])
    return out


def _role_perms_many(role_ids):
    """Олон дүрийн эрхийг НЭГ query-ээр: {role_id: [permission, ...]} (эрхгүй бол [])."""
    out = {rid: [] for rid in role_ids}
    if not role_ids:
        return out
    stmt = (select(RolePermission.role_id.label("_role_id"), *Permission.__table__.c)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_(list(role_ids)))
            .order_by(RolePermission.role_id, Permission.id))
    for r in session().execute(stmt).mappings():
        perm = dict(r)
        out[perm.pop("_role_id")].append(perm)
    return out


def _role_perms(rid):
    """Тухайн дүрийн бүх эрхийг буцаана."""
    return _role_perms_many([rid])[rid]


def _delete_by_id(model, rid, not_found):
    """`model`-оос id-аар устгана (байхгүй бол 404). Каскадыг DB өөрөө хийнэ."""
    s = session()
    count = s.execute(delete(model).where(model.id == rid)).rowcount
    s.commit()
    if count == 0:
        abort(404, description=not_found)
    return jsonify(deleted=rid)


# 400/404/409 алдааны JSON хариу нь run.py дотор app-түвшинд төвлөрсөн.
