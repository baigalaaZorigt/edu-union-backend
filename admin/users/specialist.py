"""GET /api/me/specialist — сургуулийн менежерт өөрийн сургуулийг хариуцсан Зөвлөх мэргэжилтэн.

Токен эзэмшигчийн хамрах хүрээнээс (user_scope) сургуулийг олно: `organization_id`
(Сургуулийн менежер), байхгүй бол `organization_ids`-ийн эхнийх. Дараа нь тэр сургуулийг
хамрах хүрээндээ агуулсан мэргэжилтнийг хайна:
  1. ХОН (rural) — school_type='rural' БӨГӨӨД organization_ids-д энэ сургууль байгаа.
     "rural" нь ангилал биш, сургуулийг шууд нэрлэж оноодог тул эхэлж шалгана.
  2. Бусад — school_type = сургуулийн ангиллын төрөл (SCHOOL_TYPE_CATEGORY) БӨГӨӨД
     district_au2_code = сургуулийн au2_code.
Олон таарвал хамгийн бага id. Зөвхөн идэвхтэй, "Зөвлөх мэргэжилтэн" дүртэй хэрэглэгч.
Токен шаардана, тусгай эрх шаардахгүй (core/auth.py-ийн SELF_PREFIXES — /api/me/...).
"""
import json

from flask import abort, jsonify
from sqlalchemy import select

from core.orm import session
from core.orm.models import AppUser, Organization, Role, Structure, UserScope
from core.scope_core import RURAL, SCHOOL_TYPE_CATEGORY, is_specialist, scope_of

from admin.users import bp

CATEGORY_TYPE = {cat: st for st, cat in SCHOOL_TYPE_CATEGORY.items()}   # 12 -> "general"


def _ids(raw):
    try:
        ids = json.loads(raw or "[]")
    except ValueError:
        return set()
    return {int(i) for i in ids if str(i).isdigit()} if isinstance(ids, list) else set()


def _my_organization_id():
    """Менежерийн сургууль; сургуульгүй (эсвэл өөрөө мэргэжилтэн) бол 403."""
    scope = scope_of()
    if scope and scope.get("organization_id"):
        return int(scope["organization_id"])
    if scope and scope.get("organization_ids") and scope.get("school_type") != RURAL:
        return int(scope["organization_ids"][0])
    abort(403, description="Зөвхөн сургуулийн менежерт — таны хамрах хүрээнд сургууль алга")


def _specialists():
    """Идэвхтэй, хамрах хүрээтэй Зөвлөх мэргэжилтнүүд (id-аар эрэмбэлсэн)."""
    rows = session().execute(
        select(AppUser.id, AppUser.last_name, AppUser.first_name, AppUser.email,
               Role.name.label("role_name"), Structure.name.label("structure_name"),
               Structure.code.label("structure_code"), UserScope.school_type,
               UserScope.district_au2_code, UserScope.organization_ids)
        .join(UserScope, UserScope.user_id == AppUser.id)
        .join(Role, Role.id == AppUser.role_id)
        .outerjoin(Structure, Structure.id == AppUser.structure_id)
        .where(AppUser.is_active == 1)
        .order_by(AppUser.id)).mappings().all()
    return [r for r in rows if is_specialist(r)]


def find_specialist(org):
    """Байгууллагыг хариуцсан мэргэжилтэн (эсвэл None) ба таарсан шалтгаан."""
    people = _specialists()
    for p in people:
        if p["school_type"] == RURAL and org.id in _ids(p["organization_ids"]):
            return p, "rural"
    school_type = CATEGORY_TYPE.get(org.school_category_id)
    if school_type and org.au2_code:
        for p in people:
            if p["school_type"] == school_type and p["district_au2_code"] == org.au2_code:
                return p, "district"
    return None, None


@bp.route("/api/me/specialist", methods=["GET"])
def my_specialist():
    org = session().get(Organization, _my_organization_id())
    if org is None:
        abort(404, description="Таны сургууль олдсонгүй")
    person, matched_by = find_specialist(org)
    if person is None:
        abort(404, description="Таны сургуулийг хариуцсан мэргэжилтэн олдсонгүй")
    return jsonify({"id": person["id"], "last_name": person["last_name"],
                    "first_name": person["first_name"], "email": person["email"],
                    "structure_name": person["structure_name"],
                    "structure_code": person["structure_code"],
                    "organization_id": org.id, "matched_by": matched_by})
