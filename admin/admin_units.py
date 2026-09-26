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

from core.db import get_db
from core.helpers import rows, require, json_body, fail, pick, insert_row, update_row

bp = Blueprint("admin_units", __name__)


# ===================== admin_unit1/2/3 (Аймаг / Сум / Баг) =====================
# prefix   — URL болон endpoint-ийн нэр (/api/au1, list_au1 ...)
# key      — TEXT анхдагч түлхүүр, name — засаж болох цорын ганц талбар
# create   — POST-д заавал талбарууд (INSERT-ийн баганууд мөн эдгээр)
# parent   — (эцэг хүснэгт, түлхүүр багана, хүсэлтийн талбар, алдааны мессеж)
# filters  — жагсаалтын шүүлтүүрүүд; эхнийх нь өгөгдсөн бол түүгээр л шүүнэ
ADMIN_UNITS = (
    {"prefix": "au1", "table": "admin_unit1", "key": "code", "name": "name",
     "create": ("code", "name"), "parent": None, "filters": (),
     "not_found": "Аймаг олдсонгүй",
     "conflict": "Энэ код аль хэдийн бүртгэгдсэн байна"},
    {"prefix": "au2", "table": "admin_unit2", "key": "au2_code", "name": "au2_name",
     "create": ("au2_code", "au2_name", "au1_code"),
     "parent": ("admin_unit1", "code", "au1_code", "au1_code (эцэг аймаг) олдсонгүй"),
     "filters": ("au1_code",),
     "not_found": "Сум олдсонгүй",
     "conflict": "Энэ сумын код аль хэдийн бүртгэгдсэн байна"},
    {"prefix": "au3", "table": "admin_unit3", "key": "au3_code", "name": "au3_name",
     "create": ("au3_code", "au3_name", "au1_code", "au2_code"),
     "parent": ("admin_unit2", "au2_code", "au2_code", "au2_code (эцэг сум) олдсонгүй"),
     "filters": ("au2_code", "au1_code"),
     "not_found": "Баг олдсонгүй",
     "conflict": "Энэ багийн код аль хэдийн бүртгэгдсэн байна"},
)


def _register_unit(u):
    """Нэг түвшний list/get/create/update/delete маршрутуудыг bp дээр бүртгэнэ."""
    table, key, name = u["table"], u["key"], u["name"]

    def list_units():
        sql, params = f"SELECT * FROM {table}", ()
        for f in u["filters"]:
            value = request.args.get(f)
            if value:
                sql, params = sql + f" WHERE {f}=?", (value,)
                break
        conn = get_db()
        data = rows(conn.execute(sql + f" ORDER BY {key}", params).fetchall())
        conn.close()
        return jsonify(data)

    def get_unit(code):
        conn = get_db()
        row = conn.execute(f"SELECT * FROM {table} WHERE {key}=?", (code,)).fetchone()
        conn.close()
        if not row:
            abort(404, description=u["not_found"])
        return jsonify(dict(row))

    def create_unit():
        data = request.get_json(silent=True)
        require(data, u["create"])
        conn = get_db()
        if u["parent"]:
            p_table, p_key, field, message = u["parent"]
            if not conn.execute(f"SELECT 1 FROM {p_table} WHERE {p_key}=?",
                                (data[field],)).fetchone():
                fail(conn, 400, message)
        try:
            insert_row(conn, table, {f: data[f] for f in u["create"]})
            conn.commit()
        except Exception:
            fail(conn, 409, u["conflict"])
        conn.close()
        return jsonify(data), 201

    def update_unit(code):
        data = request.get_json(silent=True)
        require(data, [name])
        conn = get_db()
        count = update_row(conn, table, code, {name: data[name]}, key=key)
        conn.commit()
        conn.close()
        if count == 0:
            abort(404, description=u["not_found"])
        return jsonify({key: code, name: data[name]})

    def delete_unit(code):
        conn = get_db()
        cur = conn.execute(f"DELETE FROM {table} WHERE {key}=?", (code,))
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            abort(404, description=u["not_found"])
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
SCHOOL_CATEGORY_SELECT = "SELECT sc.*, printf('%02d', sc.id) AS code FROM school_category sc"
MAX_SCHOOL_CATEGORY_ID = 99


@bp.route("/api/school_category", methods=["GET"])
def list_school_category():
    conn = get_db()
    data = rows(conn.execute(SCHOOL_CATEGORY_SELECT + " ORDER BY sc.id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/school_category/<int:cid>", methods=["GET"])
def get_school_category(cid):
    conn = get_db()
    row = conn.execute(SCHOOL_CATEGORY_SELECT + " WHERE sc.id=?", (cid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(dict(row))


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
    conn = get_db()
    try:
        new_id = insert_row(conn, "school_category", values)
        conn.commit()
    except Exception:
        fail(conn, 409, "Энэ id аль хэдийн бүртгэгдсэн байна")
    new_id = data.get("id") or new_id
    row = conn.execute(SCHOOL_CATEGORY_SELECT + " WHERE sc.id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/school_category/<int:cid>", methods=["PUT", "PATCH"])
def update_school_category(cid):
    values = pick(json_body(), SCHOOL_CATEGORY_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    count = update_row(conn, "school_category", cid, values)
    conn.commit()
    conn.close()
    if count == 0:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(updated=cid, fields=list(values))


@bp.route("/api/school_category/<int:cid>", methods=["DELETE"])
def delete_school_category(cid):
    conn = get_db()
    cur = conn.execute("DELETE FROM school_category WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(deleted=cid)
