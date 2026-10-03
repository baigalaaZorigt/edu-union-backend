"""member (Гишүүн) — CRUD, эвлэлийн картын дугаар, хамрах хүрээ."""
from datetime import datetime

from flask import jsonify, request, abort
from sqlalchemy import select

from core.helpers import json_body, list_json, pick, require
from core.orm import session
from core.orm.models import (Contact, Member, MemberEducation, MemberFile, MemberReward,
                             Organization, Position, Profession, SalaryScale, SchoolCategory)
from core.orm.query import paginate
from core.scope_core import check_member_scope, check_org_scope, member_clause

from admin.union import bp
from admin.union.common import (CARD_CODE_LEN, MEMBER_REWARD_QUERY, _check_au, _check_ref,
                                _create, _delete_by_id, _digit_code, _org_full_code,
                                _purge_orphan_contacts, _require_row,
                                _update_by_id, full_code)
from admin.union.member_education import EDUCATION_QUERY


# Гишүүний бүртгэлийн талбарууд (organization_id-аас бусад, оруулж/засаж болох).
# Боловсрол (#10) нь member_education, утас/факс (#11) нь contact хүснэгтэд
# (owner_type='member') олноор бүртгэгдэнэ.
# union_card_number энд БАЙХГҮЙ — тэр нь union_card_code-оос автоматаар бүрдэнэ.
MEMBER_FIELDS = (
    "last_name", "first_name", "birth_date", "gender", "register_number",
    "union_card_code", "union_joined_date", "member_status", "status",
    "position_id", "profession_id", "salary_scale_id", "email",
    "au1_code", "au2_code", "au3_code", "address_detail", "signature", "is_active",
)

# Гишүүнийг лавлах + байгууллагын нэртэй нь хамт унших select; 5 оронтой
# organization_code-г member_row() Python-д бодно (DB-ээс хамааралгүй).
MEMBER_QUERY = (
    select(*Member.__table__.c,
           Position.name.label("position_name"),
           Profession.name.label("profession_name"),
           SalaryScale.code.label("salary_scale_code"),
           SalaryScale.salary.label("salary_scale_salary"),
           Organization.school_category_id.label("_org_category"),
           Organization.org_code.label("_org_code"),
           SchoolCategory.short_name.label("school_category_short_name"),
           Organization.name.label("organization_name"))
    .select_from(Member)                # ORM entity — soft delete шүүлт үйлчилнэ
    .outerjoin(Position, Position.id == Member.position_id)
    .outerjoin(Profession, Profession.id == Member.profession_id)
    .outerjoin(SalaryScale, SalaryScale.id == Member.salary_scale_id)
    .outerjoin(Organization, Organization.id == Member.organization_id)
    .outerjoin(SchoolCategory, SchoolCategory.id == Organization.school_category_id))
NOT_FOUND = "Гишүүн олдсонгүй"


def member_row(mapping):
    """MEMBER_QUERY-ийн мөр -> JSON dict (+ байгууллагын 5 оронтой organization_code)."""
    d = dict(mapping)
    d["organization_code"] = full_code(d.pop("_org_category"), d.pop("_org_code"))
    return d


def _card_number(org_id, card_code):
    """Гишүүний 9 оронтой батламжийн дугаар = байгууллагын 5 орон + гишүүний 4 орон."""
    full = _org_full_code(org_id)
    if not full:
        abort(400, description="Байгууллагад сургуулийн ангилал ба 3 оронтой код (org_code) "
                               "тохируулаагүй тул батламжийн дугаар үүсгэх боломжгүй")
    return full + card_code


def _check_card_unique(card_number, member_id=None):
    """Батламжийн 9 оронтой дугаар давхардаж байвал 409."""
    stmt = select(Member.id).where(Member.union_card_number == card_number)
    if member_id is not None:
        stmt = stmt.where(Member.id != member_id)
    if session().scalar(stmt.limit(1)) is not None:
        abort(409, description=f"Батламжийн дугаар {card_number} аль хэдийн бүртгэгдсэн байна")


# Заавал бөглөх талбарууд (member-required-fields-spec): POST-д бүгд байх ёстой;
# PUT/PATCH нь хэсэгчилсэн тул ИЛГЭЭСЭН талбарыг л хоосон/буруу болгохыг хориглоно.
REQUIRED_TEXT = (("last_name", "Овог"), ("first_name", "Нэр"), ("gender", "Хүйс"),
                 ("status", "Статус"))


def _validate_required(data, creating):
    """Овог, нэр, хүйс, төрсөн огноо, статус — хоосон биш; birth_date нь YYYY-MM-DD."""
    for field, label in REQUIRED_TEXT:
        if field not in data and not creating:
            continue
        val = data.get(field)
        if not isinstance(val, str) or not val.strip():
            abort(400, description=f"{label} ({field}) заавал бөглөнө")
        data[field] = val.strip()
    if "birth_date" in data or creating:
        val = data.get("birth_date")
        try:
            data["birth_date"] = datetime.strptime(str(val or "").strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            abort(400, description="Төрсөн огноо (birth_date) заавал, YYYY-MM-DD хэлбэрээр "
                                   "(ж: '1990-05-17')")


def _validate_member(data, creating=False):
    """Гишүүний JSON-ы энгийн шалгалт (DB холболт нээхээс ӨМНӨ дуудна).

    - member_status / status: лавлахгүй, гараас бичих ЧӨЛӨӨТ ТЕКСТ
    - union_card_code: яг 4 оронтой тоо (энэ нь union_card_number-ийн сүүлийн 4 орон)
    - is_active / signature: зөвхөн 0 эсвэл 1 (true/false-ыг хөрвүүлнэ)
    """
    for flag in ("is_active", "signature"):
        val = data.get(flag)
        if val is None:
            continue
        if not (isinstance(val, bool) or val in (0, 1, "0", "1")):
            abort(400, description=f"{flag} нь 0 эсвэл 1 байна")
        data[flag] = int(val)
    _validate_required(data, creating)
    for field in ("member_status", "status"):
        st = data.get(field)
        if st is not None and (not isinstance(st, str) or not st.strip()):
            abort(400, description=f"{field} зөвхөн текст байна (ж: 'идэвхтэй')")
    # union_card_number гараар бичигдэхгүй — union_card_code(4)-оос автоматаар бүрдэнэ
    if "union_card_number" in data:
        abort(400, description=(
            "union_card_number-г шууд өгөхгүй — 4 оронтой union_card_code илгээнэ "
            "(байгууллагын 5 оронтой кодтой нийлж 9 орон болно)"))
    if data.get("union_card_code") is not None:
        data["union_card_code"] = _digit_code(
            data["union_card_code"], CARD_CODE_LEN, "union_card_code")


def _member_refs(data):
    """Гишүүний лавлах холбоосуудыг (албан тушаал, мэргэжил, цалингийн шатлал) шалгана."""
    _check_ref(data, "position_id", Position, "Албан тушаал")
    _check_ref(data, "profession_id", Profession, "Мэргэжил")
    _check_ref(data, "salary_scale_id", SalaryScale, "Цалингийн шатлал")


def _read(mid):
    row = session().execute(MEMBER_QUERY.where(Member.id == mid)).mappings().first()
    return member_row(row) if row else None


# ======================= member (Гишүүн) =======================
@bp.route("/api/member", methods=["GET"])
def list_member():
    items, meta = paginate(member_list_query(), mappings=True)
    return list_json([member_row(m) for m in items], meta)


def member_list_query():
    """GET /api/member-ийн select — шүүлт + хамрах хүрээ. Excel экспорт (export.py)
    ЯГ ЭНИЙГ ашиглана, тиймээс файл жагсаалттай ижил мөрүүдийг агуулна.

    ?organization_id= ба ?is_active= (0/1) шүүлтүүд — хосолж болно.
    """
    cond = []
    if request.args.get("organization_id"):
        cond.append(Member.organization_id == request.args["organization_id"])
    if request.args.get("is_active") is not None:
        cond.append(Member.is_active ==
                    (1 if request.args["is_active"] in ("1", "true", "True") else 0))
    # Хамрах хүрээ — гишүүн нь харьяа байгууллагаараа дамжин шүүгдэнэ (спек §5)
    scope = member_clause()
    if scope is not None:
        cond.append(scope)
    return MEMBER_QUERY.where(*cond).order_by(Member.id)


@bp.route("/api/member/<int:mid>", methods=["GET"])
def get_member(mid):
    check_member_scope(mid)
    out = _read(mid)
    if out is None:
        abort(404, description=NOT_FOUND)
    s = session()
    # Боловсролыг зэргийн нэртэй нь хамт буцаана
    out["educations"] = [dict(r) for r in s.execute(
        EDUCATION_QUERY.where(MemberEducation.member_id == mid)
        .order_by(MemberEducation.id)).mappings()]
    # Утас/факс/и-мэйл нь олон байж болно — contact-оос (owner_type='member')
    out["contacts"] = [c.to_dict() for c in s.scalars(
        select(Contact).where(Contact.owner_type == "member", Contact.owner_id == mid)
        .order_by(Contact.id))]
    # Шагнал, урамшуулал (олон байж болно) — төрлийнх нь нэртэй хамт
    out["rewards"] = [dict(r) for r in s.execute(
        MEMBER_REWARD_QUERY.where(MemberReward.member_id == mid)
        .order_by(MemberReward.id)).mappings()]
    # Хавсаргасан PDF файлууд (батламж г.м.)
    out["files"] = [f.to_dict() for f in s.scalars(
        select(MemberFile).where(MemberFile.member_id == mid).order_by(MemberFile.id))]
    return jsonify(out)


@bp.route("/api/member", methods=["POST"])
def create_member():
    data = request.get_json(silent=True)
    require(data, ["organization_id"])
    _validate_member(data, creating=True)
    _require_row(Organization.id, data["organization_id"],
                 "organization_id (эцэг байгууллага) олдсонгүй")
    check_org_scope(data["organization_id"])
    _member_refs(data)
    _check_au(data)
    values = {"organization_id": data["organization_id"],
              **pick(data, MEMBER_FIELDS, skip_none=True)}
    # 4 оронтой код өгсөн бол 9 оронтой батламжийн дугаарыг үүсгэнэ
    if data.get("union_card_code") is not None:
        card = _card_number(data["organization_id"], data["union_card_code"])
        _check_card_unique(card)
        values["union_card_number"] = card
    return _create(Member, values, read=_read)


@bp.route("/api/member/<int:mid>", methods=["PUT", "PATCH"])
def update_member(mid):
    data = json_body()
    _validate_member(data)
    values = pick(data, MEMBER_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    check_member_scope(mid)
    _member_refs(data)
    _check_au(data)
    # 4 оронтой кодыг сольсон бол 9 оронтой дугаарыг дахин үүсгэнэ
    if data.get("union_card_code") is not None:
        org_id = session().scalar(select(Member.organization_id).where(Member.id == mid))
        if org_id is None:
            abort(404, description=NOT_FOUND)
        card = _card_number(org_id, data["union_card_code"])
        _check_card_unique(card, mid)
        values["union_card_number"] = card
    return _update_by_id(Member, mid, values, NOT_FOUND)


@bp.route("/api/member/<int:mid>", methods=["DELETE"])
def delete_member(mid):
    check_member_scope(mid)
    return _delete_by_id(Member, mid, NOT_FOUND, _purge_orphan_contacts)
