"""Лавлах хүснэгтүүд: education_degree, position, profession, reward_type, structure."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import fail, insert_row, json_body, pick, require, update_row

from admin.union import bp
from admin.union.common import _delete_by_id, _get_one, _list_rows


# Кодтой лавлах хүснэгтүүдийн талбарууд (id-аас бусад)
CODED_REF_FIELDS = ("code", "name")
DEGREE_NOT_FOUND = "Боловсролын зэрэг олдсонгүй"
ID_TAKEN = "Энэ id аль хэдийн бүртгэгдсэн байна"

# Лавлахын мөрийг устгахад ямар баганууд NULL болох ёстой вэ.
# ON DELETE SET NULL нь ЗӨВХӨН шинэ DB дээр ажиллана: хуучин DB дээр эдгээр
# багана нь ALTER TABLE ADD COLUMN-оор нэмэгдсэн бөгөөд SQLite тэгж FK үүсгэж
# чаддаггүй. Тиймээс хоёр тохиолдолд ижил ажиллуулахын тулд гараар цэвэрлэнэ.
REF_CLEAR_REFS = {
    "structure": (("organization", "structure_id"), ("app_user", "structure_id")),
    "position": (("member", "position_id"),),
    "profession": (("member", "profession_id"),),
    "reward_type": (("member_reward", "reward_type_id"),),
}


def _insert_with_id(conn, table, values, data):
    """`values` (+ өгсөн бол гараар сонгосон `id`)-г нэмээд шинэ мөрийг буцаана → 201.

    Лавлахууд seed-ээс өөрийн id-тай ирдэг тул id давхцвал 409.
    """
    if data.get("id") is not None:
        values = {**values, "id": data["id"]}
    try:
        new_id = insert_row(conn, table, values)
        conn.commit()
    except Exception:
        fail(conn, 409, ID_TAKEN)
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?",
                       (data.get("id") or new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


# ================ education_degree (Боловсролын зэрэг, лавлах) ================
@bp.route("/api/education_degree", methods=["GET"])
def list_education_degree():
    return _list_rows("SELECT * FROM education_degree ORDER BY id")


@bp.route("/api/education_degree/<int:eid>", methods=["GET"])
def get_education_degree(eid):
    return _get_one("SELECT * FROM education_degree WHERE id=?", (eid,), DEGREE_NOT_FOUND)


@bp.route("/api/education_degree", methods=["POST"])
def create_education_degree():
    data = request.get_json(silent=True)
    require(data, ["name"])
    return _insert_with_id(get_db(), "education_degree", {"name": data["name"]}, data)


@bp.route("/api/education_degree/<int:eid>", methods=["PUT", "PATCH"])
def update_education_degree(eid):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    count = update_row(conn, "education_degree", eid, {"name": data["name"]})
    conn.commit()
    conn.close()
    if count == 0:
        abort(404, description=DEGREE_NOT_FOUND)
    return jsonify(id=eid, name=data["name"])


@bp.route("/api/education_degree/<int:eid>", methods=["DELETE"])
def delete_education_degree(eid):
    return _delete_by_id(get_db(), "education_degree", eid, DEGREE_NOT_FOUND)


# ====== Кодтой лавлахууд (position / profession / reward_type / structure) ======
# Бүгд ижил бүтэцтэй (id + code + name) тул CRUD-ыг доорх туслахууд хуваалцана.
def _check_code_unique(conn, table, code, label, exclude_id=None):
    """Лавлахын код давхцсан эсэхийг шалгана (DB-д UNIQUE байхгүй тул гараар, 409)."""
    if code is None or code == "":
        return
    sql, params = f"SELECT 1 FROM {table} WHERE code=?", [code]
    if exclude_id is not None:
        sql += " AND id<>?"
        params.append(exclude_id)
    if conn.execute(sql, params).fetchone():
        fail(conn, 409, f"{label}: '{code}' код аль хэдийн бүртгэгдсэн байна")


def _ref_list(table):
    return _list_rows(f"SELECT * FROM {table} ORDER BY id")


def _ref_get(table, rid, label):
    return _get_one(f"SELECT * FROM {table} WHERE id=?", (rid,), f"{label} олдсонгүй")


def _ref_create(table, label):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    _check_code_unique(conn, table, data.get("code"), label)
    return _insert_with_id(conn, table, pick(data, CODED_REF_FIELDS, skip_none=True), data)


def _ref_update(table, rid, label):
    """code/name-ийн аль нэг эсвэл хоёуланг нь засна (хэсэгчилсэн засвар)."""
    data = json_body()
    values = pick(data, CODED_REF_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    if "name" in data and not (data["name"] or "").strip():
        abort(400, description="name хоосон байж болохгүй")
    conn = get_db()
    _check_code_unique(conn, table, data.get("code"), label, rid)
    count = update_row(conn, table, rid, values)
    conn.commit()
    if count == 0:
        fail(conn, 404, f"{label} олдсонгүй")
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
    conn.close()
    return jsonify(dict(row))


def _ref_delete(table, rid, label):
    conn = get_db()
    for ref_table, col in REF_CLEAR_REFS.get(table, ()):
        conn.execute(f"UPDATE {ref_table} SET {col}=NULL WHERE {col}=?", (rid,))
    return _delete_by_id(conn, table, rid, f"{label} олдсонгүй")


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
