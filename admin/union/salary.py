"""salary_request (Цалингийн хүсэлт) ба salary_scale (Цалингийн шатлал, лавлах)."""

from flask import jsonify, request, abort
from sqlalchemy import select, update

from core.helpers import json_body, pick, require
from core.orm import session
from core.orm.models import Member, SalaryRequest, SalaryScale

from admin.union import bp
from admin.union.common import (_arg_filters, _create, _delete_by_id, _get_one, _list_rows,
                                _require_row, _update_by_id)


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


def _apply_scale(data):
    """salary_scale_id өгсөн бол шатлалаас sector/code/position/salary-г хуулж буцаана."""
    scale_id = data.get("salary_scale_id")
    if scale_id is None:
        return data
    sc = session().scalar(select(SalaryScale).where(SalaryScale.id == scale_id))
    if sc is None:
        abort(400, description="salary_scale_id (цалингийн шатлал) олдсонгүй")
    return {**data, **{f: getattr(sc, f) for f in SALARY_SCALE_FIELDS}}


@bp.route("/api/salary_request", methods=["GET"])
def list_salary():
    cond = _arg_filters(SalaryRequest, ("member_id", "status"))
    return _list_rows(select(SalaryRequest).where(*cond).order_by(SalaryRequest.id))


@bp.route("/api/salary_request/<int:sid>", methods=["GET"])
def get_salary(sid):
    return _get_one(SalaryRequest, sid, REQUEST_NOT_FOUND)


@bp.route("/api/salary_request", methods=["POST"])
def create_salary():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    _validate_salary(data)
    _require_row(Member.id, data["member_id"], "member_id (эцэг гишүүн) олдсонгүй")
    data = _apply_scale(data)  # шатлал сонгосон бол утгыг хуулна
    # Зөвхөн дамжуулсан талбарыг оруулна — оруулаагүй бол status DB-ийн default-аар бөглөгдөнө
    values = {"member_id": data["member_id"], **pick(data, SALARY_FIELDS, skip_none=True)}
    return _create(SalaryRequest, values)


@bp.route("/api/salary_request/<int:sid>", methods=["PUT", "PATCH"])
def update_salary(sid):
    data = json_body()
    _validate_salary(data)
    data = _apply_scale(data)  # шатлал сонгосон бол sector/code/.../salary-г хуулна
    values = pick(data, SALARY_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(SalaryRequest, sid, values, REQUEST_NOT_FOUND)


@bp.route("/api/salary_request/<int:sid>", methods=["DELETE"])
def delete_salary(sid):
    return _delete_by_id(SalaryRequest, sid, REQUEST_NOT_FOUND)


# ==================== salary_scale (Цалингийн шатлал, лавлах) ====================
@bp.route("/api/salary_scale", methods=["GET"])
def list_salary_scale():
    cond = _arg_filters(SalaryScale, ("sector",))
    return _list_rows(select(SalaryScale).where(*cond).order_by(SalaryScale.id))


@bp.route("/api/salary_scale/<int:sid>", methods=["GET"])
def get_salary_scale(sid):
    return _get_one(SalaryScale, sid, SCALE_NOT_FOUND)


@bp.route("/api/salary_scale", methods=["POST"])
def create_salary_scale():
    data = request.get_json(silent=True)
    require(data, ["sector", "code"])
    s = session()
    scale = SalaryScale(**{f: data.get(f) for f in SALARY_SCALE_FIELDS})
    try:   # salary_scale.code нь UNIQUE — давхцвал 409
        s.add(scale)
        s.commit()
    except Exception:
        s.rollback()
        abort(409, description=SCALE_CODE_TAKEN)
    return jsonify(scale.to_dict()), 201


@bp.route("/api/salary_scale/<int:sid>", methods=["PUT", "PATCH"])
def update_salary_scale(sid):
    values = pick(json_body(), SALARY_SCALE_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    s = session()
    try:
        count = s.execute(update(SalaryScale).where(SalaryScale.id == sid).values(values)
                          .execution_options(synchronize_session=False)).rowcount
        s.commit()
    except Exception:
        s.rollback()
        abort(409, description=SCALE_CODE_TAKEN)
    if count == 0:
        abort(404, description=SCALE_NOT_FOUND)
    return jsonify(updated=sid, fields=list(values))


@bp.route("/api/salary_scale/<int:sid>", methods=["DELETE"])
def delete_salary_scale(sid):
    return _delete_by_id(SalaryScale, sid, SCALE_NOT_FOUND)
