"""Хамрах хүрээний домэйний цөм (хоёр site хуваалцана).

`role` нь хэрэглэгч "ЮУ хийж болох"-ыг заадаг бол `user_scope` нь "АЛЬ өгөгдлийг
харах"-ыг заана. Энэ модуль тэр хүрээг SQL нөхцөл болгон хөрвүүлж, хоёр талаас
дуудагдана:
  - `client/union.py`  — /api/member, /api/organization дээр автоматаар шүүнэ
  - `admin/users.py`   — /api/me/scope, /api/me/organizations

Дүрэм (specialist_onboarding_api_spec.md §5):
  - `organization_id` (Сургуулийн менежер) -> зөвхөн тэр НЭГ байгууллага
  - `school_type='rural'` (ХОН)            -> `organization_ids`-д багтсан байгууллагууд
  - `school_type` бусад утгатай            -> тухайн ангилал БӨГӨӨД `district_au2_code`
  - Хамрах хүрээний мөр байхгүй (admin г.м.) -> шүүлтгүй, БҮГДИЙГ харна

Шүүлт нь ДҮРНЭЭС биш, `user_scope` мөрнөөс хамаарна: тэр мөрийг зөвхөн Зөвлөх
мэргэжилтэн / Сургуулийн менежерт тохируулдаг (user_scope_api_spec.md §6) тул
admin болон бусад дүр автоматаар "шүүлтгүй" болно.
"""
import json

from flask import g, abort

# Зөвлөх мэргэжилтний дүрийн нэр — `onboarding_completed` зөвхөн энэ дүрд
# утга учиртай (спек §3.1). Харьцуулалт нь зай/том-жижиг үсгийг үл хайхарна.
SPECIALIST_ROLE = "Зөвлөх мэргэжилтэн"

RURAL = "rural"

# school_type -> school_category.id (db.py-ийн SCHOOL_CATEGORIES-ийн seed id-ууд).
# `rural` (ХОН) нь ангилал БИШ — тодорхой сургуулиудыг organization_ids-ээр сонгоно.
SCHOOL_TYPE_CATEGORY = {
    "preschool": 11,    # Сургуулийн өмнөх боловсрол (СӨБ)
    "general": 12,      # Ерөнхий боловсрол (ЕБС)
    "vocational": 13,   # Мэргэжлийн боловсрол, сургалт (МБС)
    "higher": 14,       # Их, дээд боловсрол (ИДС)
    "science": 15,      # Шинжлэх ухаан (ШУ)
}


def public_scope(row):
    """user_scope мөрийг JSON-д тохирсон dict болгоно (мөр байхгүй бол None).

    organization_ids нь DB-д JSON текстээр хадгалагддаг — гадагшаа ҮРГЭЛЖ массив.
    """
    if row is None:
        return None
    d = dict(row)
    try:
        ids = json.loads(d.get("organization_ids") or "[]")
    except ValueError:
        ids = []
    d["organization_ids"] = ids if isinstance(ids, list) else []
    return d


def load_scope(conn, uid):
    """Тухайн хэрэглэгчийн хамрах хүрээг уншина (мөр байхгүй бол None)."""
    return public_scope(
        conn.execute("SELECT * FROM user_scope WHERE user_id=?", (uid,)).fetchone())


def is_specialist(row):
    """Мөр нь Зөвлөх мэргэжилтэн дүртэй хэрэглэгч эсэх (role_name-тэй SELECT шаардна)."""
    try:
        name = row["role_name"]
    except (KeyError, IndexError, TypeError):
        name = None
    return (name or "").strip().casefold() == SPECIALIST_ROLE.casefold()


def current_scope(conn, user=None):
    """Хүсэлт тавьсан (эсвэл өгсөн) хэрэглэгчийн хамрах хүрээ. Токенгүй бол None."""
    u = user if user is not None else getattr(g, "user", None)
    if u is None:
        return None
    return load_scope(conn, u["id"])


def _org_where(scope):
    """Хамрах хүрээ -> `organization` хүснэгтэд тавих WHERE нөхцөл, параметрүүд.

    Буцаах нөхцөл:
      None    — шүүлт хийхгүй (бүх байгууллага)
      "0 = 1" — нэг ч байгууллага харагдахгүй (ж: ХОН боловч сургууль оноогоогүй)
    """
    if not scope:
        return None, []
    if scope.get("organization_id"):            # Сургуулийн менежер — яг нэг сургууль
        return "id = ?", [scope["organization_id"]]
    st = scope.get("school_type")
    if st == RURAL:                             # ХОН — гараар сонгосон сургуулиуд
        ids = scope.get("organization_ids") or []
        if not ids:
            return "0 = 1", []
        return f"id IN ({', '.join('?' * len(ids))})", list(ids)
    if st:                                      # Ангилал + дүүрэг
        cat = SCHOOL_TYPE_CATEGORY.get(st)
        if cat is None:
            return "0 = 1", []
        cond, params = "school_category_id = ?", [cat]
        if scope.get("district_au2_code"):
            cond += " AND au2_code = ?"
            params.append(scope["district_au2_code"])
        return cond, params
    return None, []                             # хоосон хүрээ — шүүлтгүй


def org_condition(conn, alias="o", user=None):
    """Байгууллагын жагсаалтад тавих нөхцөл: (sql | None, params)."""
    cond, params = _org_where(current_scope(conn, user))
    if cond is None:
        return None, []
    return f"{alias}.id IN (SELECT id FROM organization WHERE {cond})", params


def member_condition(conn, alias="m", user=None):
    """Гишүүдийн жагсаалтад тавих нөхцөл: (sql | None, params).

    Гишүүн нь харьяа байгууллагаараа дамжин хамрах хүрээнд оршино.
    """
    cond, params = _org_where(current_scope(conn, user))
    if cond is None:
        return None, []
    return (f"{alias}.organization_id IN (SELECT id FROM organization WHERE {cond})",
            params)


def require_org_in_scope(conn, oid, user=None):
    """Байгууллага хамрах хүрээнд байгаа эсэхийг шалгана (эс бөгөөс conn хаагаад 403)."""
    cond, params = _org_where(current_scope(conn, user))
    if cond is None:
        return
    if not conn.execute(f"SELECT 1 FROM organization WHERE ({cond}) AND id=?",
                        params + [oid]).fetchone():
        conn.close()
        abort(403, description="Энэ байгууллага таны хамрах хүрээнд байхгүй")


def require_member_in_scope(conn, mid, user=None):
    """Гишүүн хамрах хүрээнд байгаа эсэхийг шалгана (эс бөгөөс conn хаагаад 403).

    Гишүүн байхгүй бол шүүлт хийхгүй — 404-ийг маршрут өөрөө буцаана.
    """
    cond, params = _org_where(current_scope(conn, user))
    if cond is None:
        return
    row = conn.execute("SELECT organization_id FROM member WHERE id=?", (mid,)).fetchone()
    if row is None:
        return
    if not conn.execute(f"SELECT 1 FROM organization WHERE ({cond}) AND id=?",
                        params + [row["organization_id"]]).fetchone():
        conn.close()
        abort(403, description="Энэ гишүүн таны хамрах хүрээнд байхгүй")
