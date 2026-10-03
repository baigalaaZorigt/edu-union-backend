"""user_scope (Хамрах хүрээ) — /api/user/<id>/scope (user_scope_api_spec.md)."""
import json

from flask import jsonify, request, abort
from sqlalchemy import delete

from core.helpers import json_body
from core.orm import session
from core.orm.models import AdminUnit2, AppUser, Organization, UserScope
from core.scope_core import RURAL, SCHOOL_TYPE_CATEGORY

from admin.users import bp
from admin.users.common import SCHOOL_TYPES, _exists, _now, check_user_access, load_scope


# Төрөл бүрд (ХОН ч, ангилал ч) тодорхой сургуулиудыг organization_ids-ээр сонгоно
# (specialist-scope-multiselect-spec). district_au2_code нь ангилалтай төрөлд зөвхөн
# сонголтын шүүлтүүр болж хадгалагдана; organization_ids хоосон үед л ХУУЧИН "бүхэл дүүрэг"
# утгаараа үйлчилнэ (өмнө нь хадгалсан мөрүүд, хуучин frontend).
SCOPE_FIELDS = ("school_type", "district_au2_code", "organization_ids", "organization_id")
EMPTY_SCOPE = {"school_type": None, "district_au2_code": None,
               "organization_ids": [], "organization_id": None}


def _require_user(uid):
    if not _exists(AppUser, uid):
        abort(404, description="Хэрэглэгч олдсонгүй")


def _validate_scope(s):
    """Хамрах хүрээний бизнес дүрмүүд (user_scope_api_spec.md §6). Зөрвөл 400."""
    def bad(msg):
        abort(400, description=msg)

    st = s["school_type"]
    if st is not None and st not in SCHOOL_TYPES:
        bad("school_type буруу байна: " + ", ".join(SCHOOL_TYPES))

    ids = s["organization_ids"]
    if ids is None:
        ids = []
    if not isinstance(ids, list):
        bad("organization_ids нь массив байх ёстой")
    try:
        ids = s["organization_ids"] = [int(x) for x in ids]
    except (TypeError, ValueError):
        bad("organization_ids нь бүхэл тооны массив байх ёстой")

    district = s["district_au2_code"]
    if st == RURAL:
        if district:
            bad("school_type='rural' үед district_au2_code сонгохгүй "
                "(тодорхой сургуулиудыг organization_ids-ээр сонгоно)")
    elif st is not None and not ids and not district:
        bad(f"school_type='{st}' үед organization_ids-ээр дор хаяж нэг сургууль сонгоно")

    if district and not _exists(AdminUnit2, district):
        bad("district_au2_code (дүүрэг) олдсонгүй")

    category = SCHOOL_TYPE_CATEGORY.get(st)          # rural / төрөлгүй бол None
    for oid in ids:
        org = session().get(Organization, oid)
        if org is None:
            bad(f"organization_ids: {oid} дугаартай байгууллага олдсонгүй")
        if category is not None and org.school_category_id != category:
            bad(f"organization_ids: {oid} дугаартай байгууллага school_type='{st}' ангилалд "
                "хамаарахгүй")

    if s["organization_id"] is not None and not _exists(Organization, s["organization_id"]):
        bad("organization_id (сургууль) олдсонгүй")


# ============ user_scope (Хамрах хүрээ) — user_scope_api_spec.md ============
# Маршрутын БИЕ нь /api/user/<uid>/scope (админ) ба /api/me/scope (өөрөө)
# хоёрт хуваалцагдана — ялгаа нь зөвхөн АЛЬ хэрэглэгчийн id-г авахад.
def _scope_get(uid):
    _require_user(uid)
    return jsonify(load_scope(uid))          # мөр байхгүй бол null


def _scope_save(uid):
    """Хамрах хүрээг хадгална (upsert).

    PUT   — БҮХЭЛД нь дарж бичнэ (илгээгээгүй талбар хоосон болно).
    PATCH — зөвхөн илгээсэн талбарыг сольж, бусдыг нь хэвээр үлдээнэ.
    """
    data = json_body()
    _require_user(uid)
    scope = dict(EMPTY_SCOPE)
    if request.method == "PATCH":
        scope.update({k: v for k, v in (load_scope(uid) or {}).items()
                      if k in SCOPE_FIELDS})
    scope.update({f: data[f] for f in SCOPE_FIELDS if f in data})
    _validate_scope(scope)
    s = session()
    row = s.get(UserScope, uid)
    if row is None:
        row = UserScope(user_id=uid)
        s.add(row)
    row.school_type = scope["school_type"]
    row.district_au2_code = scope["district_au2_code"]
    row.organization_ids = json.dumps(scope["organization_ids"])
    row.organization_id = scope["organization_id"]
    row.updated_at = _now()
    s.commit()
    return jsonify(load_scope(uid))


def _scope_delete(uid):
    _require_user(uid)
    s = session()
    count = s.execute(delete(UserScope).where(UserScope.user_id == uid)).rowcount
    s.commit()
    if count == 0:
        abort(404, description="Хамрах хүрээ бүртгэгдээгүй байна")
    return jsonify(deleted=uid)


@bp.route("/api/user/<int:uid>/scope", methods=["GET"])
def get_user_scope(uid):
    check_user_access(uid)
    return _scope_get(uid)


@bp.route("/api/user/<int:uid>/scope", methods=["PUT", "PATCH"])
def save_user_scope(uid):
    check_user_access(uid)
    return _scope_save(uid)


@bp.route("/api/user/<int:uid>/scope", methods=["DELETE"])
def delete_user_scope(uid):
    check_user_access(uid)
    return _scope_delete(uid)
