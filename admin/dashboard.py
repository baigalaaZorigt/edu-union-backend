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

from db import get_db
from helpers import rows
from scope_core import org_condition, member_condition

bp = Blueprint("admin_dashboard", __name__)


def _where(cond):
    return (" WHERE " + cond) if cond else ""


@bp.route("/api/admin/dashboard/summary", methods=["GET"])
def summary():
    """Нийт тоо + ангиллаар + хүйсээр (спек §3)."""
    conn = get_db()
    # Хамрах хүрээ: байгууллагад o.id-гаар, гишүүнд m.organization_id-гаар
    org_cond, org_args = org_condition(conn, alias="o")
    mem_cond, mem_args = member_condition(conn, alias="m")

    total_orgs = conn.execute(
        "SELECT COUNT(*) FROM organization o" + _where(org_cond), org_args).fetchone()[0]
    total_members = conn.execute(
        "SELECT COUNT(*) FROM member m" + _where(mem_cond), mem_args).fetchone()[0]

    # Ангилал бүрээр: байгууллагын тоо ба тэдгээрийн гишүүдийн тоо.
    # Дэд query-ууд нь хамрах хүрээний нөхцөлийг өөртөө агуулна.
    by_category = rows(conn.execute(
        "SELECT sc.id AS school_category_id, sc.short_name, sc.full_name, "
        "  (SELECT COUNT(*) FROM organization o "
        f"    WHERE o.school_category_id = sc.id{' AND ' + org_cond if org_cond else ''}) "
        "    AS organization_count, "
        "  (SELECT COUNT(*) FROM member m JOIN organization o ON o.id = m.organization_id "
        f"    WHERE o.school_category_id = sc.id{' AND ' + mem_cond if mem_cond else ''}) "
        "    AS member_count "
        "FROM school_category sc ORDER BY sc.id",
        org_args + mem_args).fetchall())

    # Хүйс — member.gender-ийн "эр" / "эм" утгаар (спек §3)
    gender = conn.execute(
        "SELECT SUM(CASE WHEN m.gender='эр' THEN 1 ELSE 0 END) AS male, "
        "       SUM(CASE WHEN m.gender='эм' THEN 1 ELSE 0 END) AS female "
        "  FROM member m" + _where(mem_cond), mem_args).fetchone()
    conn.close()

    return jsonify(
        total_members=total_members,
        total_organizations=total_orgs,
        by_category=by_category,
        gender={"male": gender["male"] or 0, "female": gender["female"] or 0},
    )
