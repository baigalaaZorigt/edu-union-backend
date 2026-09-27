"""horoo (Хороо) — CRUD."""

from flask import jsonify, request, abort
from sqlalchemy import select

from core.helpers import json_body, pick, require
from core.orm import session
from core.orm.models import Contact, Holboo, Horoo

from admin.union import bp
from admin.union.common import (_arg_filters, _create, _delete_by_id, _list_rows,
                                _purge_orphan_contacts, _purge_orphan_files,
                                _require_row, _update_by_id)


# Хорооны талбарууд (holboo_id-аас бусад)
HOROO_FIELDS = ("name", "type", "registration_number", "founded_date")
NOT_FOUND = "Хороо олдсонгүй"


@bp.route("/api/horoo", methods=["GET"])
def list_horoo():
    return _list_rows(select(Horoo).where(*_arg_filters(Horoo, ("holboo_id",)))
                      .order_by(Horoo.id))


@bp.route("/api/horoo/<int:hid>", methods=["GET"])
def get_horoo(hid):
    s = session()
    horoo = s.get(Horoo, hid)
    if horoo is None:
        abort(404, description=NOT_FOUND)
    out = horoo.to_dict()
    out["contacts"] = [c.to_dict() for c in s.scalars(
        select(Contact).where(Contact.owner_type == "horoo", Contact.owner_id == hid)
        .order_by(Contact.id))]
    return jsonify(out)


@bp.route("/api/horoo", methods=["POST"])
def create_horoo():
    data = request.get_json(silent=True)
    require(data, ["holboo_id", "name"])
    _require_row(Holboo.id, data["holboo_id"], "holboo_id (эцэг холбоо) олдсонгүй")
    values = {"holboo_id": data["holboo_id"], **pick(data, HOROO_FIELDS, skip_none=True)}
    return _create(Horoo, values)


@bp.route("/api/horoo/<int:hid>", methods=["PUT", "PATCH"])
def update_horoo(hid):
    values = pick(json_body(), HOROO_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(Horoo, hid, values, NOT_FOUND)


@bp.route("/api/horoo/<int:hid>", methods=["DELETE"])
def delete_horoo(hid):
    return _delete_by_id(Horoo, hid, NOT_FOUND, _purge_orphan_contacts, _purge_orphan_files)
