"""Хамрах хүрээний домэйний цөм (хоёр site хуваалцана).

`role` нь хэрэглэгч "ЮУ хийж болох"-ыг заадаг бол `user_scope` нь "АЛЬ өгөгдлийг
харах"-ыг заана. Энэ модуль тэр хүрээг ORM (SQLAlchemy) нөхцөл болгон хөрвүүлж, хоёр талаас
дуудагдана:
  - `admin/union/`     — /api/member, /api/organization дээр автоматаар шүүнэ
  - `admin/users.py`   — /api/me/scope, /api/me/organizations

Дүрэм (specialist_onboarding_api_spec.md §5):
  - `organization_id` (Сургуулийн менежер) -> зөвхөн тэр НЭГ байгууллага
  - `school_type='rural'` (ХОН)            -> `organization_ids`-д багтсан байгууллагууд
  - `school_type` бусад утгатай            -> `organization_ids` (сонгосон сургуулиуд);
    жагсаалт ХООСОН хуучин мөр             -> тухайн ангилал БӨГӨӨД `district_au2_code`
  - Хамрах хүрээний мөр байхгүй (admin г.м.) -> шүүлтгүй, БҮГДИЙГ харна

Шүүлт нь ДҮРНЭЭС биш, `user_scope` мөрнөөс хамаарна: тэр мөрийг зөвхөн Зөвлөх
мэргэжилтэн / Сургуулийн менежерт тохируулдаг (user_scope_api_spec.md §6) тул
admin болон бусад дүр автоматаар "шүүлтгүй" болно.
"""
import json

from flask import abort, g
from sqlalchemy import false, select

from core.orm import session
from core.orm.models import AdminUnit2, Member, Organization, UserScope

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


def is_specialist(row):
    """Мөр нь Зөвлөх мэргэжилтэн дүртэй хэрэглэгч эсэх (role_name-тэй SELECT шаардна)."""
    try:
        name = row["role_name"]
    except (KeyError, IndexError, TypeError):
        name = None
    return (name or "").strip().casefold() == SPECIALIST_ROLE.casefold()


# ====================== Хамрах хүрээ -> ORM нөхцөл ======================
def scope_of(user=None):
    """Хэрэглэгчийн хамрах хүрээ (dict) — ORM-оор. Токенгүй эсвэл мөргүй бол None."""
    u = user if user is not None else getattr(g, "user", None)
    if u is None:
        return None
    row = session().get(UserScope, u["id"])
    return public_scope(row.to_dict()) if row is not None else None


def org_clause(user=None):
    """Organization-д тавих ORM нөхцөл; None = шүүлтгүй, false() = юу ч харагдахгүй."""
    scope = scope_of(user)
    if not scope:
        return None
    if scope.get("organization_id"):            # Сургуулийн менежер — яг нэг сургууль
        return Organization.id == scope["organization_id"]
    st = scope.get("school_type")
    ids = scope.get("organization_ids") or []
    if st == RURAL:                             # ХОН — гараар сонгосон сургуулиуд
        return Organization.id.in_(ids) if ids else false()
    if st and ids:                              # Ангилал — гараар сонгосон сургуулиуд
        return Organization.id.in_(ids)
    if st:                                      # Хуучин мөр: ангилал + бүхэл дүүрэг
        cat = SCHOOL_TYPE_CATEGORY.get(st)
        if cat is None:
            return false()
        cond = Organization.school_category_id == cat
        if scope.get("district_au2_code"):
            cond = cond & (Organization.au2_code == scope["district_au2_code"])
        return cond
    return None


def member_clause(user=None):
    """Member-д тавих ORM нөхцөл (харьяа байгууллагаараа); None = шүүлтгүй."""
    cond = org_clause(user)
    if cond is None:
        return None
    return Member.organization_id.in_(select(Organization.id).where(cond))


def check_org_scope(oid, user=None):
    """Байгууллага хүрээнд байхгүй бол 403."""
    cond = org_clause(user)
    if cond is not None and session().scalar(
            select(Organization.id).where(cond, Organization.id == oid)) is None:
        abort(403, description="Энэ байгууллага таны хамрах хүрээнд байхгүй")


def check_member_scope(mid, user=None):
    """Гишүүн хүрээнд байхгүй бол 403 (гишүүн байхгүй бол шүүхгүй — 404-ийг маршрут өгнө)."""
    if org_clause(user) is None:
        return
    member = session().get(Member, mid)
    if member is not None:
        try:
            check_org_scope(member.organization_id, user)
        except Exception as exc:                # мессежийг гишүүнийх болгоно
            if getattr(exc, "code", None) == 403:
                abort(403, description="Энэ гишүүн таны хамрах хүрээнд байхгүй")
            raise


# ====================== Байгууллага бичих (үүсгэх/засах) ======================
def check_org_write(values, creating, user=None):
    """Хүрээтэй хэрэглэгч байгууллагыг ХҮРЭЭНЭЭСЭЭ ГАДУУР бүртгэж/зөөж болохгүй -> 403.

    - `district_au2_code` оноосон бол хаяг (au2_code, өгсөн бол au1_code) яг тэр сум/дүүрэг;
    - ангилалтай (rural биш) бол school_category_id нь тэр ангилал;
    - Сургуулийн менежер (нэг сургууль) шинэ байгууллага бүртгэхгүй.
    Үүсгэхэд бүгдийг, засахад зөвхөн ИЛГЭЭСЭН талбарыг шалгана. Хүрээгүй (admin) бол шалгахгүй.
    """
    scope = scope_of(user)
    if not scope:
        return
    if scope.get("organization_id"):
        if creating:
            abort(403, description="Таны хамрах хүрээ нэг байгууллага — шинэ байгууллага "
                                   "бүртгэх боломжгүй")
        return
    district = scope.get("district_au2_code")
    if district:
        if (creating or "au2_code" in values) and str(values.get("au2_code") or "") != district:
            abort(403, description=f"Хаяг таны хамрах хүрээнд байхгүй — зөвхөн өөрт оноосон "
                                   f"сум/дүүрэг (au2_code={district})-ийг сонгоно")
        if values.get("au1_code"):
            au2 = session().get(AdminUnit2, district)
            if au2 is not None and str(values["au1_code"]) != au2.au1_code:
                abort(403, description="Хаяг таны хамрах хүрээнд байхгүй — аймаг/нийслэл "
                                       f"(au1_code) нь {au2.au1_code} байна")
    cat = SCHOOL_TYPE_CATEGORY.get(scope.get("school_type"))
    if cat is not None and (creating or "school_category_id" in values) \
            and values.get("school_category_id") != cat:
        abort(403, description="Сургуулийн ангилал таны хамрах хүрээнд байхгүй — "
                               f"school_category_id={cat} байна")


def adopt_org(oid, user=None):
    """Сонгосон сургуулиудаар (organization_ids) хүрээлэгдсэн хэрэглэгчийн ШИНЭ байгууллагыг
    жагсаалтад нь нэмнэ — эс бөгөөс өөрийн бүртгэснээ харахгүй. Хуучин "бүхэл дүүрэг" мөрөнд
    хэрэггүй (ангилал + дүүргээрээ аль хэдийн харагдана). Commit-ыг дуудагч хийнэ."""
    u = user if user is not None else getattr(g, "user", None)
    row = session().get(UserScope, u["id"]) if u else None
    if row is None or row.organization_id:
        return
    ids = public_scope(row.to_dict())["organization_ids"]
    if (ids or row.school_type == RURAL) and oid not in ids:
        row.organization_ids = json.dumps(ids + [oid])
