"""organization (Гишүүн байгууллага) — CRUD, бүртгэлийн код, хамрах хүрээ."""

from flask import jsonify, request, abort
from sqlalchemy import case, func, select, update

from core.helpers import json_body, list_json, pick, require
from core.orm import session
from core.orm.models import Contact, Member, Organization, SchoolCategory, Structure
from core.orm.query import paginate
from core.scope_core import check_org_scope, org_clause

from admin.union import bp
from admin.union.common import (_arg_filters, _check_au, _check_ref, _create, _delete_by_id,
                                _digit_code, _org_full_code, _purge_orphan_contacts,
                                _purge_orphan_files, category_code, full_code, under35_cutoff)


# --- Бүртгэлийн кодын бүтэц ---
# Сургуулийн ангилал (2) + байгууллагын код (3)          = байгууллагын код (5)
# байгууллагын код (5)  + гишүүний код (4)               = union_card_number (9)
ORG_CODE_LEN = 3          # organization.org_code — гараас

# Байгууллагын бүх талбар (зөвхөн эдгээрийг л оруулж/засна)
ORG_FIELDS = (
    "name", "school_category_id", "org_code",
    "registration_number", "state_reg_number", "founded_date",
    "activity_code", "activity_name", "parent_org",
    "au1_code", "au2_code", "au3_code", "address_detail", "postal_address",
    "phone1", "phone2", "email", "contact_name", "structure_id",
)

# Байгууллагыг сургуулийн ангилал + бүтцийн нэртэй нь хамт унших select; 2 оронтой
# school_category_code ба 5 оронтой full_code-г org_row() Python-д бодно (DB-ээс хамааралгүй).
ORG_QUERY = (
    select(*Organization.__table__.c,
           Structure.name.label("structure_name"),
           Structure.code.label("structure_code"),
           SchoolCategory.short_name.label("school_category_short_name"),
           SchoolCategory.full_name.label("school_category_name"))
    .outerjoin(SchoolCategory, SchoolCategory.id == Organization.school_category_id)
    .outerjoin(Structure, Structure.id == Organization.structure_id))
NOT_FOUND = "Байгууллага олдсонгүй"


def org_row(mapping):
    """ORG_QUERY-ийн мөр -> JSON dict (+ school_category_code, full_code)."""
    d = dict(mapping)
    d["school_category_code"] = category_code(d["school_category_id"])
    d["full_code"] = full_code(d["school_category_id"], d["org_code"])
    return d


def org_stats_many(org_ids):
    """Олон байгууллагын гишүүдийн нийт / эмэгтэй / 35-аас доош тоог НЭГ query-ээр.

    Өмнө нь байгууллага бүрд тусдаа query (N+1) — PG дээр бүр нь сүлжээгээр явдаг байв.
    Гишүүнгүй байгууллага 0-ээр гарна.
    """
    zero = {"total_members": 0, "female_members": 0, "under35_members": 0}
    if not org_ids:
        return {}
    out = {oid: dict(zero) for oid in org_ids}
    cutoff = under35_cutoff()
    for r in session().execute(
            select(Member.organization_id,
                   func.count().label("total"),
                   func.sum(case((Member.gender == "эм", 1), else_=0)).label("female"),
                   func.sum(case((Member.birth_date.is_not(None) & (Member.birth_date > cutoff), 1),
                                 else_=0)).label("under35"))
            .where(Member.organization_id.in_(list(org_ids)))
            .group_by(Member.organization_id)):
        out[r.organization_id] = {"total_members": r.total or 0,
                                  "female_members": r.female or 0,
                                  "under35_members": r.under35 or 0}
    return out


def org_stats(org_id):
    """Нэг байгууллагын гишүүдийн тоо (org_stats_many-ийн нэг элементтэй хувилбар)."""
    return org_stats_many([org_id])[org_id]


# =================== organization (Гишүүн байгууллага) ===================
@bp.route("/api/organization", methods=["GET"])
def list_org():
    items, meta = paginate(org_list_query(), mappings=True)
    data = [org_row(m) for m in items]
    stats = org_stats_many([o["id"] for o in data])   # хуудасны мөрүүдэд, нэг query
    for o in data:
        o.update(stats[o["id"]])
    return list_json(data, meta)


def org_list_query():
    """GET /api/organization-ийн select — шүүлт + хамрах хүрээ (Excel экспорт ч ашиглана).

    ?school_category_id= ба ?structure_id= шүүлтүүр — хосолж болно.
    """
    cond = _arg_filters(Organization, ("school_category_id", "structure_id"))
    scope = org_clause()        # Хамрах хүрээ — серверийн талд НЭМЭГДЭХ нөхцөл (спек §5)
    if scope is not None:
        cond.append(scope)
    return ORG_QUERY.where(*cond).order_by(Organization.id)


def _read(oid):
    """Нэг байгууллага (join + код) — байхгүй бол None."""
    row = session().execute(ORG_QUERY.where(Organization.id == oid)).mappings().first()
    return org_row(row) if row else None


@bp.route("/api/organization/<int:oid>", methods=["GET"])
def get_org(oid):
    check_org_scope(oid)
    out = _read(oid)
    if out is None:
        abort(404, description=NOT_FOUND)
    out.update(org_stats(oid))
    out["contacts"] = [c.to_dict() for c in session().scalars(
        select(Contact).where(Contact.owner_type == "organization", Contact.owner_id == oid)
        .order_by(Contact.id))]
    return jsonify(out)


def _validate_org(data):
    """org_code (3 орон) ба school_category_id-г шалгаж, тоон утга болгоно — DB нээхээс өмнө.

    Маягтаас ангилал нь "12" гэсэн ТЕКСТ хэлбэрээр ирдэг тул int болгож хэвийтгэнэ
    (эс бөгөөс кодын харьцуулалт/форматлалт дээр л мэдэгддэг алдаа үүснэ).
    Хоосон мөр ("") нь "утга алга" гэсэн үг — NULL болгож хадгална.
    """
    if data.get("org_code") is not None:
        data["org_code"] = _digit_code(data["org_code"], ORG_CODE_LEN, "org_code")
    if "school_category_id" in data:
        cat = data["school_category_id"]
        if isinstance(cat, str):
            cat = cat.strip() or None
        if cat is not None:
            try:
                cat = int(cat)
            except (TypeError, ValueError):
                abort(400, description="school_category_id нь бүхэл тоо байх ёстой")
        data["school_category_id"] = cat


def _check_org_code_unique(data, oid=None):
    """Ангилал+код (5 орон) давхардвал 409 — гишүүдийн батламжийн дугаар давхцахаас сэргийлнэ.

    Засварлах үед зөвхөн нэг хэсгийг нь илгээж болох тул дутуу хэсгийг DB-ээс нөхнө.
    """
    s = session()
    cat, code = data.get("school_category_id"), data.get("org_code")
    if oid is not None and (cat is None or code is None):
        cur = s.execute(select(Organization.school_category_id, Organization.org_code)
                        .where(Organization.id == oid)).first()
        if cur:
            cat = cur.school_category_id if cat is None else cat
            code = cur.org_code if code is None else code
    if cat is None or not code:
        return
    stmt = select(Organization.id).where(Organization.school_category_id == cat,
                                         Organization.org_code == code)
    if oid is not None:
        stmt = stmt.where(Organization.id != oid)
    if s.scalar(stmt.limit(1)) is not None:
        abort(409, description=f"{cat:02d}{code} код өөр байгууллагад бүртгэгдсэн байна")


def _recompute_cards(oid):
    """Байгууллагын код өөрчлөгдөхөд гишүүдийн 9 оронтой дугаарыг дахин бодно."""
    full = _org_full_code(oid)
    stmt = update(Member).where(Member.organization_id == oid)
    if full:
        stmt = (stmt.where(Member.union_card_code.is_not(None))
                .values(union_card_number=full + Member.union_card_code))
    else:   # ангилал/код нь дутуу болсон бол дугаарыг цэвэрлэнэ
        stmt = stmt.values(union_card_number=None)
    session().execute(stmt.execution_options(synchronize_session=False))


def _check_org_refs(data, oid=None):
    """Байгууллагын лавлах холбоос, 5 оронтой кодын давхцал, хаягийг шалгана."""
    _check_ref(data, "school_category_id", SchoolCategory, "Сургуулийн ангилал")
    _check_ref(data, "structure_id", Structure, "Бүтцийн удирдлага")
    _check_org_code_unique(data, oid)
    _check_au(data)


@bp.route("/api/organization", methods=["POST"])
def create_org():
    data = request.get_json(silent=True)
    require(data, ["name"])
    _validate_org(data)
    _check_org_refs(data)
    return _create(Organization, {f: data.get(f) for f in ORG_FIELDS}, read=_read)


@bp.route("/api/organization/<int:oid>", methods=["PUT", "PATCH"])
def update_org(oid):
    data = json_body()
    _validate_org(data)
    values = pick(data, ORG_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    check_org_scope(oid)
    _check_org_refs(data, oid)
    s = session()
    count = s.execute(update(Organization).where(Organization.id == oid).values(values)
                      .execution_options(synchronize_session=False)).rowcount
    # Кодын аль нэг хэсэг өөрчлөгдвөл гишүүдийн батламжийн дугаарыг дахин бодно
    if count and ("org_code" in values or "school_category_id" in values):
        _recompute_cards(oid)
    s.commit()
    if count == 0:
        abort(404, description=NOT_FOUND)
    return jsonify(updated=oid, fields=list(values))


@bp.route("/api/organization/<int:oid>", methods=["DELETE"])
def delete_org(oid):
    check_org_scope(oid)
    return _delete_by_id(Organization, oid, NOT_FOUND,
                         _purge_orphan_contacts, _purge_orphan_files)
