"""member_education (Гишүүний боловсрол) — нэг гишүүн ОЛОН мөртэй байж болно."""

from flask import request

from core.db import get_db
from core.helpers import fail, json_body, pick, require

from admin.union import bp
from admin.union.common import (_create, _delete_by_id, _get_one, _list_rows,
                                _require_row, _update_by_id)


# Гишүүний боловсролын мөрийн талбарууд (member_id-аас бусад)
MEMBER_EDUCATION_FIELDS = ("education_degree_id", "school", "profession", "graduation_year")
NOT_FOUND = "Боловсролын бүртгэл олдсонгүй"


def _check_degree(conn, data):
    """education_degree_id өгсөн бол лавлахад байгаа эсэхийг шалгана."""
    if data.get("education_degree_id") is not None:
        _require_row(conn, "education_degree", data["education_degree_id"],
                     "education_degree_id (боловсролын зэрэг) олдсонгүй")


@bp.route("/api/member_education", methods=["GET"])
def list_member_education():
    sql = ("SELECT me.*, ed.name AS education_degree_name "
           "FROM member_education me "
           "LEFT JOIN education_degree ed ON ed.id = me.education_degree_id")
    params = []
    if request.args.get("member_id"):
        sql += " WHERE me.member_id=?"
        params.append(request.args["member_id"])
    return _list_rows(sql + " ORDER BY me.id", params)


@bp.route("/api/member_education/<int:eid>", methods=["GET"])
def get_member_education(eid):
    return _get_one("SELECT * FROM member_education WHERE id=?", (eid,), NOT_FOUND)


@bp.route("/api/member_education", methods=["POST"])
def create_member_education():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    conn = get_db()
    _require_row(conn, "member", data["member_id"], "member_id (эцэг гишүүн) олдсонгүй")
    _check_degree(conn, data)
    values = {"member_id": data["member_id"],
              **pick(data, MEMBER_EDUCATION_FIELDS, skip_none=True)}
    return _create(conn, "member_education", values,
                   "SELECT * FROM member_education WHERE id=?")


@bp.route("/api/member_education/<int:eid>", methods=["PUT", "PATCH"])
def update_member_education(eid):
    data = json_body()
    conn = get_db()
    _check_degree(conn, data)
    values = pick(data, MEMBER_EDUCATION_FIELDS)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга")
    return _update_by_id(conn, "member_education", eid, values, NOT_FOUND)


@bp.route("/api/member_education/<int:eid>", methods=["DELETE"])
def delete_member_education(eid):
    return _delete_by_id(get_db(), "member_education", eid, NOT_FOUND)

