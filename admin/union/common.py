"""ҮЭ-ийн модулиудын хуваалцсан тогтмол, query ба туслах функцууд (SQLAlchemy ORM).

Маршрутын модулиуд (horoo, organization, member, ...) бүгд ижил хэв маягтай CRUD
тул list/get/create/update/delete-ийн давтагддаг биеийг доорх `_list_rows`,
`_get_one`, `_create`, `_update_by_id`, `_delete_by_id` хуваалцана. Хүсэлтийн
session-ийг teardown хаадаг тул abort()-ийн өмнө холболт хаах шаардлагагүй.
"""
import os
from datetime import datetime, timedelta, timezone

from flask import abort, jsonify, request
from sqlalchemy import and_, delete, or_, select, update

from core.helpers import list_json
from core.orm import session
from core.orm.models import (AdminUnit1, AdminUnit2, AdminUnit3, Contact, Horoo, Member,
                             MemberReward, Organization, RewardType)
from core.orm.query import paginate
from core.storage import Area


# --- Гишүүний хавсралт файл (батламж г.м.) ---
# Production-д S3-т (core/storage.py, S3_BUCKET), локал/тестэд UPLOAD_DIR хавтсанд
# `<member_id>/<uuid>.pdf` нэрээр хадгална. Хэмжээ/төрлийн шалгалт member_file.py-д.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "member"))
MEMBER_STORE = Area("member", UPLOAD_DIR)

# --- Бүртгэлийн кодын бүтэц ---
# Сургуулийн ангилал (2) + байгууллагын код (3)          = байгууллагын код (5)
# байгууллагын код (5)  + гишүүний код (4)               = union_card_number (9)
# (ORG_CODE_LEN нь organization.py-д)
CARD_CODE_LEN = 4         # member.union_card_code — гараас

# Гишүүний шагналыг төрлийнх нь нэр/кодтой хамт унших select (мөр бүр dict-mapping)
MEMBER_REWARD_QUERY = (
    select(*MemberReward.__table__.c,
           RewardType.name.label("reward_type_name"),
           RewardType.code.label("reward_type_code"))
    .select_from(MemberReward)          # ORM entity — soft delete шүүлт үйлчилнэ
    .outerjoin(RewardType, RewardType.id == MemberReward.reward_type_id))

# contact-ийн owner_type (= хүснэгтийн нэр) -> model
OWNER_MODELS = {"horoo": Horoo, "organization": Organization, "member": Member}


# ----------------------------- Кодын тооцоо -----------------------------
def category_code(cat):
    """school_category_id -> 2 оронтой текст ("12"); ангилалгүй бол None."""
    return None if cat is None else f"{int(cat):02d}"


def full_code(cat, org_code):
    """Байгууллагын 5 оронтой код = ангилал (2) + org_code (3); аль нэг нь NULL бол None."""
    if cat is None or org_code is None:
        return None
    return category_code(cat) + org_code


def under35_cutoff():
    """35-аас доош насны хил: төрсөн огноо (ISO текст) үүнээс ХОЙШ бол 35 хүрээгүй.

    Өмнөх `(julianday('now') - julianday(birth_date))/365.25 < 35`-тэй ижил — өдрийн
    дундах цагийг ч тооцно (ISO мөрийн харьцуулалт, DB-ээс хамааралгүй).
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - timedelta(days=35 * 365.25)).strftime("%Y-%m-%d %H:%M:%S")


# ------------------------- Ерөнхий CRUD туслахууд -------------------------
def _arg_filters(model, fields):
    """?field=утга шүүлтүүдээс (хоосон бол алгасна) ORM нөхцлийн жагсаалт бүтээнэ."""
    return [getattr(model, f) == request.args[f] for f in fields if request.args.get(f)]


def _rows(items):
    """paginate()-ийн үр дүн (model эсвэл mapping) -> dict-үүдийн жагсаалт."""
    return [i.to_dict() if hasattr(i, "to_dict") else dict(i) for i in items]


def _list_rows(stmt, mappings=False, convert=None):
    """select()-ийн мөрүүдийг JSON-оор (?page=/?per_page= өгвөл хуудаслаж) буцаана."""
    items, meta = paginate(stmt, mappings=mappings)
    data = _rows(items)
    if convert:
        data = [convert(d) for d in data]
    return list_json(data, meta)


def _get_one(model, rid, not_found):
    """Анхдагч түлхүүрээр нэг мөрийг JSON-оор (байхгүй бол 404 `not_found`)."""
    obj = session().get(model, rid)
    if obj is None:
        abort(404, description=not_found)
    return jsonify(obj.to_dict())


def _create(model, values, read=None):
    """Мөр нэмээд commit хийнэ → 201. `read(id)` өгвөл (join-той) буцааж уншина."""
    s = session()
    obj = model(**values)
    s.add(obj)
    s.commit()
    return jsonify(read(obj.id) if read else obj.to_dict()), 201


def _update_by_id(model, rid, values, not_found):
    """`values`-ээр нэг мөрийг шинэчилнэ → {updated, fields} (мөр байхгүй бол 404)."""
    s = session()
    count = s.execute(update(model).where(model.id == rid).values(values)
                      .execution_options(synchronize_session=False)).rowcount
    s.commit()
    if count == 0:
        abort(404, description=not_found)
    return jsonify(updated=rid, fields=list(values))


def _delete_by_id(model, rid, not_found, *cleanups):
    """Нэг мөрийг устгана → {deleted} (байхгүй бол 404).

    Устгасан бол `cleanups` (ж: өнчин contact/файл цэвэрлэх) commit-оос өмнө ажиллана.
    DB-ийн FK каскад (ON DELETE CASCADE / SET NULL) хэвээр ажиллана.
    """
    s = session()
    count = s.execute(delete(model).where(model.id == rid)
                      .execution_options(synchronize_session=False)).rowcount
    if count:
        for cleanup in cleanups:
            cleanup()
    s.commit()
    if count == 0:
        abort(404, description=not_found)
    return jsonify(deleted=rid)


# ----------------------------- Шалгалтууд -----------------------------
def _require_row(column, value, message):
    """`column == value` мөр байгаа эсэхийг шалгана (байхгүй бол 400 `message`)."""
    if session().scalar(select(column).where(column == value).limit(1)) is None:
        abort(400, description=message)


def _check_ref(data, field, model, label):
    """Лавлах руу заасан id (ж: position_id) байгаа эсэхийг шалгана (байхгүй бол 400)."""
    if data.get(field) is not None:
        _require_row(model.id, data[field], f"{label} ({field}) олдсонгүй")


def _digit_code(value, length, label):
    """Яг `length` оронтой цифрэн код эсэхийг шалгаад текстээр буцаана (эс бөгөөс 400)."""
    code = str(value).strip()
    if not code.isdigit() or len(code) != length:
        abort(400, description=(
            f"{label} яг {length} оронтой тоо байх ёстой "
            f"(ж: '{'1'.zfill(length)}')"))
    return code


def _org_full_code(org_id):
    """Байгууллагын 5 оронтой код: ангиллын 2 орон + org_code 3 орон (дутуу бол None)."""
    row = session().execute(select(Organization.school_category_id, Organization.org_code)
                            .where(Organization.id == org_id)).first()
    if not row or row.school_category_id is None or not row.org_code:
        return None
    return f"{int(row.school_category_id):02d}{row.org_code}"


# Хаягийн талбар -> (багана, шошго)
_AU_CHECKS = (
    ("au1_code", AdminUnit1.code, "Аймаг/нийслэл (au1_code)"),
    ("au2_code", AdminUnit2.au2_code, "Сум/дүүрэг (au2_code)"),
    ("au3_code", AdminUnit3.au3_code, "Баг/хороо (au3_code)"),
)


def _check_au(data):
    """Хаягийн au1/au2/au3 код өгсөн бол засаг захиргааны нэгжид байгаа эсэхийг шалгана."""
    for field, column, label in _AU_CHECKS:
        if data.get(field):
            _require_row(column, data[field], f"{label} олдсонгүй")


# ----------------------------- Цэвэрлэгээ -----------------------------
def _purge_orphan_contacts():
    """Эзэмшигчгүй үлдсэн contact мөрүүдийг цэвэрлэнэ.

    contact нь полиморф тул FK-гүй — хороо/байгууллага/гишүүн устахад (мөн хороо
    устахад доорх байгууллага, гишүүд нь каскадаар устахад) энд гараар цэвэрлэнэ.
    """
    session().execute(delete(Contact).where(or_(*(
        and_(Contact.owner_type == owner, Contact.owner_id.not_in(select(model.id)))
        for owner, model in OWNER_MODELS.items()))).execution_options(synchronize_session=False))

