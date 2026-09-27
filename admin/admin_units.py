"""Засаг захиргааны нэгж ба сургуулийн ангиллын CRUD (Blueprint).

Гурван түвшин:
  admin_unit1 (аймаг/нийслэл)  -> code, name
  admin_unit2 (сум/дүүрэг)     -> au2_code, au2_name, au1_code
  admin_unit3 (баг/хороо)      -> au3_code, au3_name, au1_code, au2_code
Нэмэлт: school_category (сургуулийн ангилал, лавлах).

Гурван түвшний CRUD нь бараг ижил тул `ADMIN_UNITS` тодорхойлолтоос нэг л
багц функцээр (`_register_unit`) маршрутуудыг үүсгэнэ. Endpoint-ийн нэрс
(list_au1, get_au2, ...) хэвээр үлдэнэ.
"""
from flask import Blueprint, jsonify, request, abort
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.helpers import require, json_body, pick, list_json
from core.orm import session
from core.orm.models import AdminUnit1, AdminUnit2, AdminUnit3, SchoolCategory
from core.orm.query import paginate

bp = Blueprint("admin_units", __name__)


# ===================== admin_unit1/2/3 (Аймаг / Сум / Баг) =====================
# prefix   — URL болон endpoint-ийн нэр (/api/au1, list_au1 ...)
# key      — TEXT анхдагч түлхүүр, name — засаж болох цорын ганц талбар
# create   — POST-д заавал талбарууд (INSERT-ийн баганууд мөн эдгээр)
# parent   — (эцэг model, эцгийн түлхүүрийг агуулсан хүсэлтийн талбар, алдааны мессеж)
# same     — эцэг мөрийн ИЖИЛ байх ёстой талбар: (талбар, алдааны мессеж) — ж: багийн au1_code
#            нь эцэг сумынхтай таарах ёстой (өөр аймгийн сумд баг бүртгэгдэхгүй)
# filters  — жагсаалтын шүүлтүүрүүд; эхнийх нь өгөгдсөн бол түүгээр л шүүнэ
ADMIN_UNITS = (
    {"prefix": "au1", "model": AdminUnit1, "key": "code", "name": "name",
     "create": ("code", "name"), "parent": None, "filters": (),
     "not_found": "Аймаг олдсонгүй",
     "conflict": "Энэ код аль хэдийн бүртгэгдсэн байна"},
    {"prefix": "au2", "model": AdminUnit2, "key": "au2_code", "name": "au2_name",
     "create": ("au2_code", "au2_name", "au1_code"),
     "parent": (AdminUnit1, "au1_code", "au1_code (эцэг аймаг) олдсонгүй"),
     "filters": ("au1_code",),
     "not_found": "Сум олдсонгүй",
     "conflict": "Энэ сумын код аль хэдийн бүртгэгдсэн байна"},
    {"prefix": "au3", "model": AdminUnit3, "key": "au3_code", "name": "au3_name",
     "create": ("au3_code", "au3_name", "au1_code", "au2_code"),
     "parent": (AdminUnit2, "au2_code", "au2_code (эцэг сум) олдсонгүй"),
     "same": ("au1_code", "au1_code нь эцэг сумын аймагтай таарахгүй байна"),
     "filters": ("au2_code", "au1_code"),
     "not_found": "Баг олдсонгүй",
     "conflict": "Энэ багийн код аль хэдийн бүртгэгдсэн байна"},
)


def _register_unit(u):
    """Нэг түвшний list/get/create/update/delete маршрутуудыг bp дээр бүртгэнэ."""
    model, key, name = u["model"], u["key"], u["name"]
    key_col = getattr(model, key)

    def list_units():
        stmt = select(model)
        for f in u["filters"]:
            value = request.args.get(f)
            if value:
                stmt = stmt.where(getattr(model, f) == value)
                break
        items, meta = paginate(stmt.order_by(key_col))
        return list_json([o.to_dict() for o in items], meta)

    def get_unit(code):
        obj = session().get(model, code)
        if obj is None:
            abort(404, description=u["not_found"])
        return jsonify(obj.to_dict())

    def create_unit():
        data = request.get_json(silent=True)
        require(data, u["create"])
        s = session()
        if u["parent"]:
            p_model, field, message = u["parent"]
            parent = s.get(p_model, data[field])
            if parent is None:
                abort(400, description=message)
            same = u.get("same")
            if same and str(getattr(parent, same[0])) != str(data[same[0]]):
                abort(400, description=same[1])
        s.add(model(**{f: data[f] for f in u["create"]}))
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            abort(409, description=u["conflict"])
        return jsonify(data), 201

    def update_unit(code):
        data = request.get_json(silent=True)
        require(data, [name])
        s = session()
        obj = s.get(model, code)
        if obj is None:
            abort(404, description=u["not_found"])
        setattr(obj, name, data[name])
        s.commit()
        return jsonify({key: code, name: data[name]})

    def delete_unit(code):
        s = session()
        obj = s.get(model, code)
        if obj is None:
            abort(404, description=u["not_found"])
        s.delete(obj)                      # хүүхэд нэгжүүд DB-ийн ON DELETE CASCADE-аар
        s.commit()
        return jsonify(deleted=code)

    base, p = f"/api/{u['prefix']}", u["prefix"]
    # URL хувьсагчийн нэр хуучнаараа (<code>, <au2_code>, <au3_code>) үлдэнэ.
    item = f"{base}/<{key}>"
    bp.add_url_rule(base, f"list_{p}", list_units, methods=["GET"])
    bp.add_url_rule(item, f"get_{p}", lambda **kw: get_unit(kw[key]), methods=["GET"])
    bp.add_url_rule(base, f"create_{p}", create_unit, methods=["POST"])
    bp.add_url_rule(item, f"update_{p}", lambda **kw: update_unit(kw[key]),
                    methods=["PUT", "PATCH"])
    bp.add_url_rule(item, f"delete_{p}", lambda **kw: delete_unit(kw[key]),
                    methods=["DELETE"])


for _unit in ADMIN_UNITS:
    _register_unit(_unit)


# ===================== school_category (Сургуулийн ангилал) =====================
SCHOOL_CATEGORY_FIELDS = ("full_name", "short_name", "english_name")

# Ангиллын id нь бүртгэлийн кодны ЭХНИЙ 2 ОРОН болно (1 -> "01"), тиймээс 1..99.
# code-г хадгалахгүй — id-аас бодогдоно (эх сурвалж нэг байхын тулд).
MAX_SCHOOL_CATEGORY_ID = 99


def _category_json(obj):
    """Ангиллын мөр + id-аас бодсон 2 оронтой code."""
    return dict(obj.to_dict(), code=f"{obj.id:02d}")


@bp.route("/api/school_category", methods=["GET"])
def list_school_category():
    items, meta = paginate(select(SchoolCategory).order_by(SchoolCategory.id))
    return list_json([_category_json(o) for o in items], meta)


@bp.route("/api/school_category/<int:cid>", methods=["GET"])
def get_school_category(cid):
    obj = session().get(SchoolCategory, cid)
    if obj is None:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(_category_json(obj))


@bp.route("/api/school_category", methods=["POST"])
def create_school_category():
    data = request.get_json(silent=True)
    require(data, ["full_name"])
    # id заавал биш — өгвөл тогтсон утгаар, эс бөгөөс автоматаар оноогдоно.
    # id нь кодны эхний 2 орон тул 1..99 хооронд байх ёстой.
    values = {}
    if data.get("id") is not None:
        try:
            cid = int(data["id"])
        except (TypeError, ValueError):
            abort(400, description="id тоо байх ёстой")
        if not 1 <= cid <= MAX_SCHOOL_CATEGORY_ID:
            abort(400, description="id нь 1-99 хооронд байна (код нь 2 орон тул)")
        values["id"] = cid
    values.update({f: data.get(f) for f in SCHOOL_CATEGORY_FIELDS})
    s = session()
    obj = SchoolCategory(**values)
    s.add(obj)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        abort(409, description="Энэ id аль хэдийн бүртгэгдсэн байна")
    return jsonify(_category_json(obj)), 201


@bp.route("/api/school_category/<int:cid>", methods=["PUT", "PATCH"])
def update_school_category(cid):
    values = pick(json_body(), SCHOOL_CATEGORY_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    s = session()
    obj = s.get(SchoolCategory, cid)
    if obj is None:
        abort(404, description="Ангилал олдсонгүй")
    for k, v in values.items():
        setattr(obj, k, v)
    s.commit()
    return jsonify(updated=cid, fields=list(values))


@bp.route("/api/school_category/<int:cid>", methods=["DELETE"])
def delete_school_category(cid):
    s = session()
    obj = s.get(SchoolCategory, cid)
    if obj is None:
        abort(404, description="Ангилал олдсонгүй")
    s.delete(obj)
    s.commit()
    return jsonify(deleted=cid)
