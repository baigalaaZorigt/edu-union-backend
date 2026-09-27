"""Хэрэглэгчийн модулиудын хуваалцсан тогтмол, SELECT ба туслах функцууд."""
from datetime import datetime, timezone

from flask import jsonify, abort
from werkzeug.security import generate_password_hash

from core.db import get_db
from core.scope_core import RURAL, SCHOOL_TYPE_CATEGORY, is_specialist, load_scope


# --- Хамрах хүрээ (user_scope, user_scope_api_spec.md) ---
# Сургуулийн төрлийн тогтвортой кодууд (бүтэн нэрийг frontend харуулна).
# rural-аас бусад бүр нь ангиллын id-тай харгалзах ёстой тул жагсаалтыг
# scope_core.SCHOOL_TYPE_CATEGORY-ЭЭС гаргана — зөрөх (шүүлт хоосон буцаах)
# боломжгүй болно.
SCHOOL_TYPES = tuple(SCHOOL_TYPE_CATEGORY) + (RURAL,)

# Хэрэглэгчийг дүр ба бүтцийн удирдлагынх нь нэртэй хамт унших SELECT
USER_SELECT = (
    "SELECT u.*, r.name AS role_name, r.code AS role_code, st.name AS structure_name, st.code AS structure_code "
    "FROM app_user u "
    "LEFT JOIN role r ON r.id = u.role_id "
    "LEFT JOIN structure st ON st.id = u.structure_id"
)


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


def _exists(conn, table, rid):
    return conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (rid,)).fetchone() is not None


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


def _user_row(conn, uid):
    return conn.execute(USER_SELECT + " WHERE u.id=?", (uid,)).fetchone()


def _user_profile(conn, row):
    """public_user + дүрээс удамшсан бодит эрхүүд + хамрах хүрээ
    (GET /api/user/<id>, /api/login, /api/me гурав ижил хэлбэртэй)."""
    out = public_user(row)
    out["permissions"] = _role_perms(conn, row["role_id"]) if row["role_id"] else []
    out["scope"] = load_scope(conn, row["id"])
    return out


def _role_perms_many(conn, role_ids):
    """Олон дүрийн эрхийг НЭГ query-ээр: {role_id: [permission, ...]} (эрхгүй бол [])."""
    out = {rid: [] for rid in role_ids}
    if not role_ids:
        return out
    ph = ", ".join("?" * len(role_ids))
    for r in conn.execute(
            f"SELECT rp.role_id AS _role_id, p.* FROM role_permission rp "
            f"JOIN permission p ON p.id = rp.permission_id "
            f"WHERE rp.role_id IN ({ph}) ORDER BY rp.role_id, p.id", list(role_ids)).fetchall():
        perm = dict(r)
        out[perm.pop("_role_id")].append(perm)
    return out


def _role_perms(conn, rid):
    """Тухайн дүрийн бүх эрхийг буцаана."""
    return _role_perms_many(conn, [rid])[rid]


def _delete_by_id(table, rid, not_found):
    """`table`-аас id-аар устгана (байхгүй бол 404)."""
    conn = get_db()
    cur = conn.execute(f"DELETE FROM {table} WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description=not_found)
    return jsonify(deleted=rid)


# 400/404/409 алдааны JSON хариу нь run.py дотор app-түвшинд төвлөрсөн.
