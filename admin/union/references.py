"""Лавлах хүснэгтүүд: education_degree, position, profession, reward_type, structure."""

from flask import jsonify, request, abort
from sqlalchemy import select, update

from core.helpers import json_body, pick, require
from core.orm import session
from core.orm.models import EducationDegree, Position, Profession, RewardType, Structure

from admin.union import bp
from admin.union.common import _delete_by_id, _get_one, _list_rows


# Кодтой лавлах хүснэгтүүдийн талбарууд (id-аас бусад)
CODED_REF_FIELDS = ("code", "name")
DEGREE_NOT_FOUND = "Боловсролын зэрэг олдсонгүй"
ID_TAKEN = "Энэ id аль хэдийн бүртгэгдсэн байна"

# Хүснэгтийн нэр -> model (маршрутууд хүснэгтийн нэрээр дууддаг)
REF_MODELS = {"position": Position, "profession": Profession,
              "reward_type": RewardType, "structure": Structure}
# code/name-аас гадна ЗААВАЛ бөглөх текст талбарууд (reward-type-category-spec): утгыг нь
# шалгахгүй (ангиллын жагсаалт frontend-д хатуу бичигдсэн), зөвхөн хоосон биш байхыг шаардана.
REF_EXTRA_FIELDS = {"reward_type": ("category",)}


def _insert_with_id(model, values, data):
    """`values` (+ өгсөн бол гараар сонгосон `id`)-г нэмээд шинэ мөрийг буцаана → 201.

    Лавлахууд seed-ээс өөрийн id-тай ирдэг тул id давхцвал 409.
    """
    if data.get("id") is not None:
        values = {**values, "id": data["id"]}
    s = session()
    obj = model(**values)
    try:
        s.add(obj)
        s.commit()
    except Exception:
        s.rollback()
        abort(409, description=ID_TAKEN)
    row = s.scalar(select(model).where(model.id == (data.get("id") or obj.id)))
    return jsonify(row.to_dict()), 201


# ================ education_degree (Боловсролын зэрэг, лавлах) ================
@bp.route("/api/education_degree", methods=["GET"])
def list_education_degree():
    return _list_rows(select(EducationDegree).order_by(EducationDegree.id))


@bp.route("/api/education_degree/<int:eid>", methods=["GET"])
def get_education_degree(eid):
    return _get_one(EducationDegree, eid, DEGREE_NOT_FOUND)


@bp.route("/api/education_degree", methods=["POST"])
def create_education_degree():
    data = request.get_json(silent=True)
    require(data, ["name"])
    return _insert_with_id(EducationDegree, {"name": data["name"]}, data)


@bp.route("/api/education_degree/<int:eid>", methods=["PUT", "PATCH"])
def update_education_degree(eid):
    data = request.get_json(silent=True)
    require(data, ["name"])
    s = session()
    count = s.execute(update(EducationDegree).where(EducationDegree.id == eid)
                      .values(name=data["name"])
                      .execution_options(synchronize_session=False)).rowcount
    s.commit()
    if count == 0:
        abort(404, description=DEGREE_NOT_FOUND)
    return jsonify(id=eid, name=data["name"])


@bp.route("/api/education_degree/<int:eid>", methods=["DELETE"])
def delete_education_degree(eid):
    return _delete_by_id(EducationDegree, eid, DEGREE_NOT_FOUND)


# ====== Кодтой лавлахууд (position / profession / reward_type / structure) ======
# Бүгд ижил бүтэцтэй (id + code + name) тул CRUD-ыг доорх туслахууд хуваалцана.
def _check_code_unique(model, code, label, exclude_id=None):
    """Лавлахын код давхцсан эсэхийг шалгана (DB-д UNIQUE байхгүй тул гараар, 409)."""
    if code is None or code == "":
        return
    stmt = select(model.id).where(model.code == code)
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    if session().scalar(stmt.limit(1)) is not None:
        abort(409, description=f"{label}: '{code}' код аль хэдийн бүртгэгдсэн байна")


def _ref_list(table):
    model = REF_MODELS[table]
    return _list_rows(select(model).order_by(model.id))


def _ref_get(table, rid, label):
    return _get_one(REF_MODELS[table], rid, f"{label} олдсонгүй")


def _clean_extra(table, data, creating):
    """Нэмэлт заавал талбарууд: POST-д бүгд, PUT/PATCH-д ИЛГЭЭСЭН нь хоосон биш (trim) → 400."""
    for field in REF_EXTRA_FIELDS.get(table, ()):
        if field not in data and not creating:
            continue
        val = data.get(field)
        if not isinstance(val, str) or not val.strip():
            abort(400, description=f"{field} заавал бөглөнө")
        data[field] = val.strip()


def _ref_fields(table):
    return CODED_REF_FIELDS + REF_EXTRA_FIELDS.get(table, ())


def _ref_create(table, label):
    data = request.get_json(silent=True)
    require(data, ["name"])
    _clean_extra(table, data, creating=True)
    model = REF_MODELS[table]
    _check_code_unique(model, data.get("code"), label)
    return _insert_with_id(model, pick(data, _ref_fields(table), skip_none=True), data)


def _ref_update(table, rid, label):
    """code/name (reward_type-д мөн category)-ийн илгээснийг л засна (хэсэгчилсэн засвар)."""
    data = json_body()
    if not pick(data, _ref_fields(table)):
        abort(400, description="Шинэчлэх талбар алга")
    _clean_extra(table, data, creating=False)        # trim хийсэн утгыг data-д буцаана
    values = pick(data, _ref_fields(table))
    if "name" in data and not (data["name"] or "").strip():
        abort(400, description="name хоосон байж болохгүй")
    model = REF_MODELS[table]
    _check_code_unique(model, data.get("code"), label, rid)
    s = session()
    count = s.execute(update(model).where(model.id == rid).values(values)
                      .execution_options(synchronize_session=False)).rowcount
    s.commit()
    if count == 0:
        abort(404, description=f"{label} олдсонгүй")
    return jsonify(s.scalar(select(model).where(model.id == rid)).to_dict())


def _ref_delete(table, rid, label):
    """Гишүүн/байгууллага/хэрэглэгч заасан бол 409 (core/orm/restrict.py) — холбоосыг
    салгаж байж устгана. Өмнө нь холбоосыг чимээгүй NULL болгодог байв."""
    return _delete_by_id(REF_MODELS[table], rid, f"{label} олдсонгүй")


# ==================== position (Албан тушаал, лавлах) ====================
@bp.route("/api/position", methods=["GET"])
def list_position():
    return _ref_list("position")


@bp.route("/api/position/<int:pid>", methods=["GET"])
def get_position(pid):
    return _ref_get("position", pid, "Албан тушаал")


@bp.route("/api/position", methods=["POST"])
def create_position():
    return _ref_create("position", "Албан тушаал")


@bp.route("/api/position/<int:pid>", methods=["PUT", "PATCH"])
def update_position(pid):
    return _ref_update("position", pid, "Албан тушаал")


@bp.route("/api/position/<int:pid>", methods=["DELETE"])
def delete_position(pid):
    return _ref_delete("position", pid, "Албан тушаал")


# ==================== profession (Мэргэжил, лавлах) ====================
@bp.route("/api/profession", methods=["GET"])
def list_profession():
    return _ref_list("profession")


@bp.route("/api/profession/<int:pid>", methods=["GET"])
def get_profession(pid):
    return _ref_get("profession", pid, "Мэргэжил")


@bp.route("/api/profession", methods=["POST"])
def create_profession():
    return _ref_create("profession", "Мэргэжил")


@bp.route("/api/profession/<int:pid>", methods=["PUT", "PATCH"])
def update_profession(pid):
    return _ref_update("profession", pid, "Мэргэжил")


@bp.route("/api/profession/<int:pid>", methods=["DELETE"])
def delete_profession(pid):
    return _ref_delete("profession", pid, "Мэргэжил")


# ============ reward_type (Шагнал, урамшууллын төрөл, лавлах) ============
@bp.route("/api/reward_type", methods=["GET"])
def list_reward_type():
    return _ref_list("reward_type")


@bp.route("/api/reward_type/<int:rid>", methods=["GET"])
def get_reward_type(rid):
    return _ref_get("reward_type", rid, "Шагналын төрөл")


@bp.route("/api/reward_type", methods=["POST"])
def create_reward_type():
    return _ref_create("reward_type", "Шагналын төрөл")


@bp.route("/api/reward_type/<int:rid>", methods=["PUT", "PATCH"])
def update_reward_type(rid):
    return _ref_update("reward_type", rid, "Шагналын төрөл")


@bp.route("/api/reward_type/<int:rid>", methods=["DELETE"])
def delete_reward_type(rid):
    return _ref_delete("reward_type", rid, "Шагналын төрөл")


# ============ structure (Бүтцийн удирдлага, лавлах) ============
# organization ба app_user хоёул эндээс сонгоно (structure_id).
@bp.route("/api/structure", methods=["GET"])
def list_structure():
    return _ref_list("structure")


@bp.route("/api/structure/<int:sid>", methods=["GET"])
def get_structure(sid):
    return _ref_get("structure", sid, "Бүтцийн удирдлага")


@bp.route("/api/structure", methods=["POST"])
def create_structure():
    return _ref_create("structure", "Бүтцийн удирдлага")


@bp.route("/api/structure/<int:sid>", methods=["PUT", "PATCH"])
def update_structure(sid):
    return _ref_update("structure", sid, "Бүтцийн удирдлага")


@bp.route("/api/structure/<int:sid>", methods=["DELETE"])
def delete_structure(sid):
    return _ref_delete("structure", sid, "Бүтцийн удирдлага")
