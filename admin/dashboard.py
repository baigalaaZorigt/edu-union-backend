"""Хянах самбарын нэгтгэсэн тоонууд (Blueprint) — dashboard_api_spec.md.

    GET /api/admin/dashboard/summary

Нэг дуудалтаар frontend-ийн бүх виджетийг цэнэглэнэ: нийт гишүүн / байгууллага,
ангилал тус бүрийн тоо (багана диаграм + 6 карт), хүйсийн харьцаа (донат).

Ангиллын жагсаалт нь ХАТУУ БИШ — `school_category` хүснэгтийн бодит мөрүүдээр
динамик (LEFT JOIN тул тоо нь 0 байсан ангилал ч харагдана).

**Хамрах хүрээгээр шүүгдэнэ** (спек §4): Зөвлөх мэргэжилтэн зөвхөн өөрийн
сургуулиудынхаа тоог харна — /api/member, /api/organization-тай ЯГ ижил
`scope_core`-ийн дүрмээр, frontend нэмэлт параметр дамжуулахгүй. Admin (хамрах
хүрээний мөргүй хэрэглэгч) бүх системийн тоог харна.
"""
from flask import Blueprint, jsonify
from sqlalchemy import case, func, select

from core.orm import session
from core.orm.models import Member, Organization, SchoolCategory
from core.scope_core import member_clause, org_clause

bp = Blueprint("admin_dashboard", __name__)


def _filtered(stmt, cond):
    """Хамрах хүрээний нөхцөл байвал select-д нэмнэ (None бол шүүлтгүй)."""
    return stmt if cond is None else stmt.where(cond)


@bp.route("/api/admin/dashboard/summary", methods=["GET"])
def summary():
    """Нийт тоо + ангиллаар + хүйсээр (спек §3)."""
    s = session()
    # Хамрах хүрээ: байгууллагад Organization-оор, гишүүнд харьяа байгууллагаар нь
    org_cond, mem_cond = org_clause(), member_clause()

    total_orgs = s.scalar(_filtered(select(func.count()).select_from(Organization), org_cond))
    total_members = s.scalar(_filtered(select(func.count()).select_from(Member), mem_cond))

    # Ангилал бүрээр: байгууллагын тоо ба тэдгээрийн гишүүдийн тоо (correlated дэд query —
    # байгууллагагүй ангилал ч 0-ээр гарна). Гишүүн нь харьяа байгууллагаараа хүрээнд
    # багтдаг тул гишүүдийн тоонд байгууллагын нөхцөлийг join-оор шууд тавина.
    org_count = _filtered(
        select(func.count(Organization.id))
        .where(Organization.school_category_id == SchoolCategory.id), org_cond
    ).correlate(SchoolCategory).scalar_subquery()
    member_count = _filtered(
        select(func.count(Member.id)).join(Organization, Organization.id == Member.organization_id)
        .where(Organization.school_category_id == SchoolCategory.id), org_cond
    ).correlate(SchoolCategory).scalar_subquery()
    by_category = [dict(r) for r in s.execute(
        select(SchoolCategory.id.label("school_category_id"), SchoolCategory.short_name,
               SchoolCategory.full_name, org_count.label("organization_count"),
               member_count.label("member_count"))
        .order_by(SchoolCategory.id)).mappings()]

    # Хүйс — member.gender-ийн "эр" / "эм" утгаар (спек §3)
    gender = s.execute(_filtered(
        select(func.sum(case((Member.gender == "эр", 1), else_=0)).label("male"),
               func.sum(case((Member.gender == "эм", 1), else_=0)).label("female")),
        mem_cond)).mappings().one()

    return jsonify(
        total_members=total_members,
        total_organizations=total_orgs,
        by_category=by_category,
        gender={"male": gender["male"] or 0, "female": gender["female"] or 0},
    )
