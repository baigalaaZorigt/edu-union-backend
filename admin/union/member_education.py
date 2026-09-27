"""member_education (Гишүүний боловсрол) — нэг гишүүн ОЛОН мөртэй байж болно."""

from flask import abort, request
from sqlalchemy import select

from core.helpers import json_body, pick, require
from core.orm.models import EducationDegree, Member, MemberEducation

from admin.union import bp
from admin.union.common import (_create, _delete_by_id, _get_one, _list_rows,
                                _require_row, _update_by_id)


# Гишүүний боловсролын мөрийн талбарууд (member_id-аас бусад)
MEMBER_EDUCATION_FIELDS = ("education_degree_id", "school", "profession", "graduation_year")
NOT_FOUND = "Боловсролын бүртгэл олдсонгүй"

# Боловсролыг зэргийн нэртэй нь хамт (member.py-ийн дэлгэрэнгүй ч ашиглана)
EDUCATION_QUERY = (
    select(*MemberEducation.__table__.c, EducationDegree.name.label("education_degree_name"))
    .select_from(MemberEducation)       # ORM entity — soft delete шүүлт үйлчилнэ
    .outerjoin(EducationDegree, EducationDegree.id == MemberEducation.education_degree_id))


def _check_degree(data):
    """education_degree_id өгсөн бол лавлахад байгаа эсэхийг шалгана."""
    if data.get("education_degree_id") is not None:
        _require_row(EducationDegree.id, data["education_degree_id"],
                     "education_degree_id (боловсролын зэрэг) олдсонгүй")


@bp.route("/api/member_education", methods=["GET"])
def list_member_education():
    stmt = EDUCATION_QUERY
    if request.args.get("member_id"):
        stmt = stmt.where(MemberEducation.member_id == request.args["member_id"])
    return _list_rows(stmt.order_by(MemberEducation.id), mappings=True)


@bp.route("/api/member_education/<int:eid>", methods=["GET"])
def get_member_education(eid):
    return _get_one(MemberEducation, eid, NOT_FOUND)


@bp.route("/api/member_education", methods=["POST"])
def create_member_education():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    _require_row(Member.id, data["member_id"], "member_id (эцэг гишүүн) олдсонгүй")
    _check_degree(data)
    values = {"member_id": data["member_id"],
              **pick(data, MEMBER_EDUCATION_FIELDS, skip_none=True)}
    return _create(MemberEducation, values)


@bp.route("/api/member_education/<int:eid>", methods=["PUT", "PATCH"])
def update_member_education(eid):
    data = json_body()
    _check_degree(data)
    values = pick(data, MEMBER_EDUCATION_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(MemberEducation, eid, values, NOT_FOUND)


@bp.route("/api/member_education/<int:eid>", methods=["DELETE"])
def delete_member_education(eid):
    return _delete_by_id(MemberEducation, eid, NOT_FOUND)
