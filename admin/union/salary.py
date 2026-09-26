"""salary_request (Цалингийн хүсэлт) ба salary_scale (Цалингийн шатлал, лавлах)."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import fail, insert_row, json_body, pick, require, update_row

from admin.union import bp
from admin.union.common import (_arg_filters, _create, _delete_by_id, _get_one, _list_rows,
                                _require_row, _update_by_id, _where)


# Цалингийн хүсэлт
SALARY_STATUSES = ("хүлээгдэж буй", "зөвшөөрсөн", "татгалзсан")
SALARY_SECTORS = ("СӨБ ба ЕБС", "Мэргэжлийн боловсрол", "Шинжлэх ухаан")
# Цалингийн хүсэлтийн засаж/оруулж болох талбарууд (member_id-аас бусад).
# sector/code/position/salary нь salary_scale_id өгсөн үед шатлалаас автоматаар хуулагдана.
SALARY_FIELDS = (
    "salary_scale_id", "sector", "code", "position", "salary",
    "status", "request_date", "note",
)
# Цалингийн шатлалын талбарууд (хүсэлт рүү хуулагдах талбарууд ч мөн эдгээр)
SALARY_SCALE_FIELDS = ("sector", "code", "position", "salary")

REQUEST_NOT_FOUND = "Цалингийн хүсэлт олдсонгүй"
SCALE_NOT_FOUND = "Цалингийн шатлал олдсонгүй"
SCALE_CODE_TAKEN = "Энэ код (code) аль хэдийн бүртгэгдсэн байна"


# ==================== salary_request (Цалингийн хүсэлт) ====================
def _validate_salary(data):
    st = data.get("status")
    if st and st not in SALARY_STATUSES:
        abort(400, description="status буруу. Сонголт: " + ", ".join(SALARY_STATUSES))
    sb = data.get("sector")
    if sb and sb not in SALARY_SECTORS:
        abort(400, description="sector буруу. Сонголт: " + ", ".join(SALARY_SECTORS))


def _apply_scale(conn, data):
    """salary_scale_id өгсөн бол шатлалаас sector/code/position/salary-г хуулж буцаана."""
    scale_id = data.get("salary_scale_id")
    if scale_id is None:
        return data
    sc = conn.execute("SELECT * FROM salary_scale WHERE id=?", (scale_id,)).fetchone()
    if not sc:
        fail(conn, 400, "salary_scale_id (цалингийн шатлал) олдсонгүй")
    return {**data, **{f: sc[f] for f in SALARY_SCALE_FIELDS}}


@bp.route("/api/salary_request", methods=["GET"])
def list_salary():
    cond, params = _arg_filters(("member_id", "status"))
    return _list_rows("SELECT * FROM salary_request" + _where(cond) + " ORDER BY id", params)


@bp.route("/api/salary_request/<int:sid>", methods=["GET"])
def get_salary(sid):
    return _get_one("SELECT * FROM salary_request WHERE id=?", (sid,), REQUEST_NOT_FOUND)


@bp.route("/api/salary_request", methods=["POST"])
def create_salary():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    _validate_salary(data)
    conn = get_db()
    _require_row(conn, "member", data["member_id"], "member_id (эцэг гишүүн) олдсонгүй")
    data = _apply_scale(conn, data)  # шатлал сонгосон бол утгыг хуулна
    # Зөвхөн дамжуулсан талбарыг оруулна — оруулаагүй бол status DB-ийн default-аар бөглөгдөнө
    values = {"member_id": data["member_id"], **pick(data, SALARY_FIELDS, skip_none=True)}
    return _create(conn, "salary_request", values, "SELECT * FROM salary_request WHERE id=?")


@bp.route("/api/salary_request/<int:sid>", methods=["PUT", "PATCH"])
def update_salary(sid):
    data = json_body()
    _validate_salary(data)
    conn = get_db()
    data = _apply_scale(conn, data)  # шатлал сонгосон бол sector/code/.../salary-г хуулна
    values = pick(data, SALARY_FIELDS)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга")
    return _update_by_id(conn, "salary_request", sid, values, REQUEST_NOT_FOUND)


@bp.route("/api/salary_request/<int:sid>", methods=["DELETE"])
def delete_salary(sid):
    return _delete_by_id(get_db(), "salary_request", sid, REQUEST_NOT_FOUND)


# ==================== salary_scale (Цалингийн шатлал, лавлах) ====================
@bp.route("/api/salary_scale", methods=["GET"])
def list_salary_scale():
    cond, params = _arg_filters(("sector",))
    return _list_rows("SELECT * FROM salary_scale" + _where(cond) + " ORDER BY id", params)


@bp.route("/api/salary_scale/<int:sid>", methods=["GET"])
def get_salary_scale(sid):
    return _get_one("SELECT * FROM salary_scale WHERE id=?", (sid,), SCALE_NOT_FOUND)


@bp.route("/api/salary_scale", methods=["POST"])
def create_salary_scale():
    data = request.get_json(silent=True)
    require(data, ["sector", "code"])
    conn = get_db()
    try:   # salary_scale.code нь UNIQUE — давхцвал 409
        new_id = insert_row(conn, "salary_scale", {f: data.get(f) for f in SALARY_SCALE_FIELDS})
        conn.commit()
    except Exception:
        fail(conn, 409, SCALE_CODE_TAKEN)
    row = conn.execute("SELECT * FROM salary_scale WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/salary_scale/<int:sid>", methods=["PUT", "PATCH"])
def update_salary_scale(sid):
    values = pick(json_body(), SALARY_SCALE_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    try:
        count = update_row(conn, "salary_scale", sid, values)
        conn.commit()
    except Exception:
        fail(conn, 409, SCALE_CODE_TAKEN)
    conn.close()
    if count == 0:
        abort(404, description=SCALE_NOT_FOUND)
    return jsonify(updated=sid, fields=list(values))


@bp.route("/api/salary_scale/<int:sid>", methods=["DELETE"])
def delete_salary_scale(sid):
    return _delete_by_id(get_db(), "salary_scale", sid, SCALE_NOT_FOUND)
