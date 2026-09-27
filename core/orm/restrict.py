"""Холбоостой мөрийг устгахаас хамгаална — 409 + юу холбоотой байгааг хэлнэ.

Ж: «Ерөнхий боловсролын сургууль» ангиллыг 12 байгууллага заасан байхад устгавал:

    409 {"error": "«ЕБС» (сургуулийн ангилал) устгах боломжгүй: үүнтэй холбоотой 12 байгууллага
                   (…) бүртгэлтэй байна. Эхлээд тэдгээрийн холбоосыг салгаж (өөр утга сонгож
                   эсвэл устгаж) байж устгана уу.",
         "references": [{"table": "organization", "label": "байгууллага",
                         "count": 12, "examples": ["1-р сургууль", ...]}]}

`RESTRICT` — ЛАВЛАХ / БҮРТГЭЛИЙН холбоосууд: эцэг мөр устахад хүүхэд нь утгаа алдах
(SET NULL, эсвэл FK-гүй логик код: au*_code, user_scope.organization_id) газрууд.
Засаг захиргааны шатлал (аймаг → сум → баг) каскадаараа устна, гэхдээ каскадаар устах сум/баг
бүр мөн шалгагдана — аль нэгийг нь байгууллага/гишүүн заасан бол бүхэлдээ 409.
Эзэмшлийн каскад (мэдээ → блок, маягт → асуулт, гишүүн → боловсрол/шагнал/файл, цэс → дэд
цэс/хуудас, дүр → role_permission) энд ОРОХГҮЙ — тэд эцэгтэйгээ хамт устсаар байна.
Аудитын баганууд (created_by/updated_by) ба мэдэгдлийн түүх (notifications.role_id) ч
хаахгүй — хэрэглэгч/дүр устсан ч түүх хэвээр.

Шалгалт `soft_delete()`-д (core/orm/soft.py) хийгддэг тул `s.delete(obj)` ба
`delete(Model)` хоёуланд, handler бүрт автоматаар үйлчилнэ. Нуугдсан (soft delete) хүүхэд
тоологдохгүй.
"""
from sqlalchemy import false, func, select
from werkzeug.exceptions import Conflict

from core.orm.models import (AdminUnit1, AdminUnit2, AdminUnit3, AppUser, EducationDegree,
                             Member, MemberEducation, MemberReward, Organization, Position,
                             Profession, RewardType, Role, SalaryRequest, SalaryScale,
                             SchoolCategory, Structure, UserScope)

EXAMPLES = 5

# эцэг model -> (эцгийн нэр томьёо, [(хүүхдийн багана, эцгийн багана, хүүхдийн нэр томьёо)])
RESTRICT = {
    SchoolCategory: ("сургуулийн ангилал", [
        (Organization.school_category_id, "id", "байгууллага")]),
    Structure: ("бүтцийн удирдлага", [
        (Organization.structure_id, "id", "байгууллага"),
        (AppUser.structure_id, "id", "хэрэглэгч")]),
    Position: ("албан тушаал", [(Member.position_id, "id", "гишүүн")]),
    Profession: ("мэргэжил", [(Member.profession_id, "id", "гишүүн")]),
    SalaryScale: ("цалингийн шатлал", [
        (Member.salary_scale_id, "id", "гишүүн"),
        (SalaryRequest.salary_scale_id, "id", "цалингийн хүсэлт")]),
    EducationDegree: ("боловсролын зэрэг", [
        (MemberEducation.education_degree_id, "id", "гишүүний боловсрол")]),
    RewardType: ("шагналын төрөл", [(MemberReward.reward_type_id, "id", "гишүүний шагнал")]),
    Role: ("дүр", [(AppUser.role_id, "id", "хэрэглэгч")]),
    Organization: ("байгууллага", [
        (Member.organization_id, "id", "гишүүн"),
        (UserScope.organization_id, "id", "хэрэглэгчийн хамрах хүрээ")]),
    AdminUnit1: ("аймаг/нийслэл", [
        (Organization.au1_code, "code", "байгууллага"),
        (Member.au1_code, "code", "гишүүн")]),
    AdminUnit2: ("сум/дүүрэг", [
        (Organization.au2_code, "au2_code", "байгууллага"),
        (Member.au2_code, "au2_code", "гишүүн"),
        (UserScope.district_au2_code, "au2_code", "хэрэглэгчийн хамрах хүрээ")]),
    AdminUnit3: ("баг/хороо", [
        (Organization.au3_code, "au3_code", "байгууллага"),
        (Member.au3_code, "au3_code", "гишүүн")]),
}


class Referenced(Conflict):
    """409 — `extra` (references) нь {"error"}-ийн хажууд JSON-д нэмэгдэнэ (core.helpers)."""

    def __init__(self, description, references):
        super().__init__(description)
        self.extra = {"references": references}


def _display(obj):
    """Мөрийг хүнд ойлгомжтой нэрээр: овог нэр / нэр / username / код / id."""
    if isinstance(obj, (Member, AppUser)) and getattr(obj, "first_name", None):
        name = f"{obj.last_name or ''} {obj.first_name}".strip()
        return f"{name} ({obj.username})" if isinstance(obj, AppUser) else name
    for attr in ("name", "au2_name", "au3_name", "full_name", "username", "code"):
        if getattr(obj, attr, None):
            return str(obj.__dict__.get(attr) or getattr(obj, attr))
    if isinstance(obj, UserScope):
        return f"хэрэглэгч #{obj.user_id}"
    return f"#{obj.id}"


def _scope_filter(child):
    """Дуудагчийн хамрах хүрээ (scope_core) — ЖИШЭЭ нэрийг зөвхөн харж болох мөрөөс авна.

    None = шүүлтгүй (admin, хүсэлтээс гадуур). Хамрах хүрээтэй хэрэглэгчид гишүүн/байгууллага
    (ба гишүүний дэд мөр) хүрээгээр шүүгдэнэ, бусад хүснэгтийн нэр огт харагдахгүй. Тоо
    (`count`) нийтээрээ хэвээр — хувь хүний мэдээлэл биш, устгах боломжгүйн шалтгаан.
    """
    from flask import has_request_context
    if not has_request_context():
        return None
    from core.scope_core import member_clause, org_clause
    org = org_clause()
    if org is None:
        return None
    if child is Organization:
        return org
    if child is Member:
        return member_clause()
    if hasattr(child, "member_id"):                  # боловсрол, шагнал, цалингийн хүсэлт
        return child.member_id.in_(select(Member.id).where(member_clause()))
    return false()


def check_references(s, obj):
    """`obj`-г харагдах (устгаагүй) мөр заасан бол Referenced (409) шиднэ."""
    rule = RESTRICT.get(type(obj))
    if rule is None:
        return
    parent_label, refs = rule
    found = []
    for col, parent_col, label in refs:
        value = getattr(obj, parent_col)
        if value is None:
            continue
        child = col.class_
        n = s.scalar(select(func.count()).select_from(child).where(col == value))
        if n:
            visible = _scope_filter(child)
            q = select(child).where(col == value)
            if visible is not None:
                q = q.where(visible)
            rows = s.scalars(q.order_by(*child.__table__.primary_key.columns).limit(EXAMPLES))
            found.append({"table": child.__table__.name, "label": label, "count": n,
                          "examples": [_display(r) for r in rows]})
    if not found:
        return
    parts = []
    for f in found:
        if not f["examples"]:                        # хамрах хүрээнээс гадуур — нэргүй
            parts.append(f"{f['count']} {f['label']}")
            continue
        more = "…" if f["count"] > len(f["examples"]) else ""
        parts.append(f"{f['count']} {f['label']} ({', '.join(f['examples'])}{more})")
    raise Referenced(
        f"«{_display(obj)}» ({parent_label}) устгах боломжгүй: үүнтэй холбоотой "
        f"{'; '.join(parts)} бүртгэлтэй байна. Эхлээд тэдгээрийн холбоосыг салгаж (өөр утга "
        f"сонгож эсвэл устгаж) байж устгана уу.", found)
