"""member_reward (Гишүүний шагнал, урамшуулал).

Нэг гишүүн ОЛОН шагналтай байж болно (member_education-тэй ижил зарчим);
төрлийг reward_type лавлахаас сонгоно.
"""

from flask import request

from core.db import get_db
from core.helpers import fail, json_body, pick, require

from admin.union import bp
from admin.union.common import (MEMBER_REWARD_SELECT, _arg_filters, _create, _delete_by_id,
                                _get_one, _list_rows, _require_row, _update_by_id, _where)


# Гишүүний шагнал, урамшууллын мөрийн талбарууд (member_id-аас бусад)
MEMBER_REWARD_FIELDS = ("reward_type_id", "description", "reward_date")
NOT_FOUND = "Шагналын бүртгэл олдсонгүй"


def _check_reward_type(conn, data):
    """reward_type_id өгсөн бол лавлахад байгаа эсэхийг шалгана."""
    if data.get("reward_type_id") is not None:
        _require_row(conn, "reward_type", data["reward_type_id"],
                     "reward_type_id (шагналын төрөл) олдсонгүй")


@bp.route("/api/member_reward", methods=["GET"])
def list_member_reward():
    # ?member_id= ба ?reward_type_id= шүүлтүүд — хосолж болно
    cond, params = _arg_filters(("member_id", "reward_type_id"), prefix="mr.")
    return _list_rows(MEMBER_REWARD_SELECT + _where(cond) + " ORDER BY mr.id", params)


@bp.route("/api/member_reward/<int:rid>", methods=["GET"])
def get_member_reward(rid):
    return _get_one(MEMBER_REWARD_SELECT + " WHERE mr.id=?", (rid,), NOT_FOUND)


@bp.route("/api/member_reward", methods=["POST"])
def create_member_reward():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    conn = get_db()
    _require_row(conn, "member", data["member_id"], "member_id (эцэг гишүүн) олдсонгүй")
    _check_reward_type(conn, data)
    values = {"member_id": data["member_id"],
              **pick(data, MEMBER_REWARD_FIELDS, skip_none=True)}
    return _create(conn, "member_reward", values, MEMBER_REWARD_SELECT + " WHERE mr.id=?")


@bp.route("/api/member_reward/<int:rid>", methods=["PUT", "PATCH"])
def update_member_reward(rid):
    data = json_body()
    conn = get_db()
    _check_reward_type(conn, data)
    values = pick(data, MEMBER_REWARD_FIELDS)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга")
    return _update_by_id(conn, "member_reward", rid, values, NOT_FOUND)


@bp.route("/api/member_reward/<int:rid>", methods=["DELETE"])
def delete_member_reward(rid):
    return _delete_by_id(get_db(), "member_reward", rid, NOT_FOUND)
