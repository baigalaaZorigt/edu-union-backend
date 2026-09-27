"""member_reward (Гишүүний шагнал, урамшуулал).

Нэг гишүүн ОЛОН шагналтай байж болно (member_education-тэй ижил зарчим);
төрлийг reward_type лавлахаас сонгоно.
"""

from flask import abort, jsonify, request

from core.helpers import json_body, pick, require
from core.orm import session
from core.orm.models import Member, MemberReward, RewardType

from admin.union import bp
from admin.union.common import (MEMBER_REWARD_QUERY, _arg_filters, _create, _delete_by_id,
                                _list_rows, _require_row, _update_by_id)


# Гишүүний шагнал, урамшууллын мөрийн талбарууд (member_id-аас бусад)
MEMBER_REWARD_FIELDS = ("reward_type_id", "description", "reward_date")
NOT_FOUND = "Шагналын бүртгэл олдсонгүй"


def _check_reward_type(data):
    """reward_type_id өгсөн бол лавлахад байгаа эсэхийг шалгана."""
    if data.get("reward_type_id") is not None:
        _require_row(RewardType.id, data["reward_type_id"],
                     "reward_type_id (шагналын төрөл) олдсонгүй")


def _read(rid):
    """Нэг шагналыг төрлийн нэр/кодтой нь (байхгүй бол None)."""
    row = session().execute(MEMBER_REWARD_QUERY.where(MemberReward.id == rid)).mappings().first()
    return dict(row) if row else None


@bp.route("/api/member_reward", methods=["GET"])
def list_member_reward():
    # ?member_id= ба ?reward_type_id= шүүлтүүд — хосолж болно
    cond = _arg_filters(MemberReward, ("member_id", "reward_type_id"))
    return _list_rows(MEMBER_REWARD_QUERY.where(*cond).order_by(MemberReward.id), mappings=True)


@bp.route("/api/member_reward/<int:rid>", methods=["GET"])
def get_member_reward(rid):
    out = _read(rid)
    if out is None:
        abort(404, description=NOT_FOUND)
    return jsonify(out)


@bp.route("/api/member_reward", methods=["POST"])
def create_member_reward():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    _require_row(Member.id, data["member_id"], "member_id (эцэг гишүүн) олдсонгүй")
    _check_reward_type(data)
    values = {"member_id": data["member_id"],
              **pick(data, MEMBER_REWARD_FIELDS, skip_none=True)}
    return _create(MemberReward, values, read=_read)


@bp.route("/api/member_reward/<int:rid>", methods=["PUT", "PATCH"])
def update_member_reward(rid):
    data = json_body()
    _check_reward_type(data)
    values = pick(data, MEMBER_REWARD_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(MemberReward, rid, values, NOT_FOUND)


@bp.route("/api/member_reward/<int:rid>", methods=["DELETE"])
def delete_member_reward(rid):
    return _delete_by_id(MemberReward, rid, NOT_FOUND)
