"""GET /api/member ба /api/organization-ийн хайлт / шүүлт / эрэмбийн whitelist
(server_list_api_spec.md §4.2, §4.3 — core/list_query.py хэрэглэнэ).

Параметрийн нэр = frontend-ийн хүснэгтийн баганын key; DB-ийн багана энд map хийгдэнэ.
Багана нь MEMBER_QUERY / ORG_QUERY-ийн join-уудаас (Organization, Position, ...) авна.
"""
import re

from sqlalchemy import String, case, cast, func, literal, select

from core.list_query import ListSpec, as_int, contains, equals, full_name, int_equals
from core.orm.models import (Contact, Member, MemberStatus, Organization, Position, Profession,
                             SchoolCategory)

# ------------------------------- member -------------------------------
STATUS_NAME = func.coalesce(MemberStatus.name, Member.status)     # member_row()-ийн `status`


def _birth_year(v):
    return Member.birth_date.startswith(f"{as_int(v, 'birth_year'):04d}-")


def _phone(v):
    """Гишүүний утас/факс — contact хүснэгтэд (owner_type='member')."""
    return Member.id.in_(select(Contact.owner_id).where(
        Contact.owner_type == "member", Contact.type.in_(("утас", "факс")),
        contains(Contact.value)(v)))


MEMBER_LIST = ListSpec(
    id=Member.id,
    search=[contains(full_name(Member)), contains(Organization.name),
            contains(Member.register_number), contains(Member.union_card_number),
            contains(Position.name), contains(Profession.name), _phone],
    filters={
        "name": contains(full_name(Member)),
        "organization": contains(Organization.name),
        "birth_year": _birth_year,
        "gender": equals(Member.gender),
        "register_number": contains(Member.register_number),
        "union_card_number": contains(Member.union_card_number),
        "member_status_id": int_equals(Member.status_id, "member_status_id"),
        "status": contains(STATUS_NAME),
        "position": contains(Position.name),
        "profession": contains(Profession.name),
        "phone_fax": _phone,
    },
    sort={
        "name": [Member.last_name, Member.first_name],
        "organization": [Organization.name],
        "birth_year": [Member.birth_date],
        "gender": [Member.gender],
        "register_number": [Member.register_number],
        "union_card_number": [Member.union_card_number],
        "union_joined_date": [Member.union_joined_date],
        "status": [STATUS_NAME],
        "position": [Position.name],
        "profession": [Profession.name],
        "created_at": [Member.created_at],
        "updated_at": [Member.updated_at],
    },
)

# ---------------------------- organization ----------------------------
_CAT = Organization.school_category_id
# 5 оронтой бүтэн код (common.full_code()-ийн SQL хувилбар): 2 оронтой ангилал + org_code
FULL_CODE = case((_CAT < 10, literal("0").concat(cast(_CAT, String))),
                 else_=cast(_CAT, String)).concat(Organization.org_code)


def _org_code(v):
    """"11-123", "11 123" -> "11123" (зөвхөн цифр/зураас/зай бол); бусад нь хэвээр."""
    if re.fullmatch(r"[\d\s-]+", v):
        v = re.sub(r"\D", "", v) or v
    return contains(FULL_CODE)(v)


def _by_members(stmt):
    """total_members-ээр эрэмбэлэх — нэг GROUP BY дэд query LEFT JOIN (мөр бүрд subquery биш)."""
    counts = (select(Member.organization_id.label("oid"), func.count().label("n"))
              .group_by(Member.organization_id).subquery())
    return (stmt.outerjoin(counts, counts.c.oid == Organization.id),
            [func.coalesce(counts.c.n, 0)])


ORG_LIST = ListSpec(
    id=Organization.id,
    search=[_org_code, contains(Organization.name), contains(Organization.registration_number),
            contains(SchoolCategory.short_name), contains(Organization.contact_name)],
    filters={
        "org_code": _org_code,
        "name": contains(Organization.name),
        "school_type": contains(SchoolCategory.short_name),
        "registration_number": contains(Organization.registration_number),
        "leader": contains(Organization.contact_name),
    },
    sort={
        "org_code": [Organization.school_category_id, Organization.org_code],
        "name": [Organization.name],
        "school_type": [SchoolCategory.short_name],
        "registration_number": [Organization.registration_number],
        "total_members": _by_members,
        "created_at": [Organization.created_at],
        "updated_at": [Organization.updated_at],
    },
)
