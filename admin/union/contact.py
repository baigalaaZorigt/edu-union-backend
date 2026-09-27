"""contact (Холбоо барих) — хороо/байгууллага/гишүүнд полиморфоор харьяалагдана."""

from flask import jsonify, request, abort
from sqlalchemy import select

from core.helpers import json_body, pick, require
from core.orm import session
from core.orm.models import Contact

from admin.union import bp
from admin.union.common import (OWNER_MODELS, _delete_by_id, _list_rows, _require_row,
                                _update_by_id)


# contact эзэмшигчийн төрлүүд — утга нь хүснэгтийн нэртэй яг таарна.
OWNER_TYPES = ("horoo", "organization", "member")
CONTACT_TYPES = ("утас", "факс", "и-мэйл")
CONTACT_FIELDS = ("type", "value", "note")          # засаж болох талбарууд
NOT_FOUND = "Холбоо барих мэдээлэл олдсонгүй"


def _bad_type():
    abort(400, description="type нь: " + ", ".join(CONTACT_TYPES))


@bp.route("/api/contact", methods=["GET"])
def list_contact():
    # Шүүлтүүр нь зөвхөн owner_type + owner_id ХОЁУЛАА ирсэн үед хэрэгжинэ
    owner_type = request.args.get("owner_type")
    owner_id = request.args.get("owner_id")
    stmt = select(Contact)
    if owner_type and owner_id:
        stmt = stmt.where(Contact.owner_type == owner_type, Contact.owner_id == owner_id)
    return _list_rows(stmt.order_by(Contact.id))


@bp.route("/api/contact", methods=["POST"])
def create_contact():
    data = request.get_json(silent=True)
    require(data, ["owner_type", "owner_id", "type", "value"])
    if data["owner_type"] not in OWNER_TYPES:
        abort(400, description="owner_type буруу. Сонголт: " + ", ".join(OWNER_TYPES))
    if data["type"] not in CONTACT_TYPES:
        _bad_type()
    # owner_type нь хүснэгтийн нэртэй ижил
    _require_row(OWNER_MODELS[data["owner_type"]].id, data["owner_id"],
                 "Эзэмшигч (owner_id) олдсонгүй")
    s = session()
    contact = Contact(owner_type=data["owner_type"], owner_id=data["owner_id"],
                      type=data["type"], value=data["value"], note=data.get("note"))
    s.add(contact)
    s.commit()
    return jsonify(id=contact.id, **data), 201


@bp.route("/api/contact/<int:cid>", methods=["PUT", "PATCH"])
def update_contact(cid):
    data = json_body()
    if data.get("type") and data["type"] not in CONTACT_TYPES:
        _bad_type()
    values = pick(data, CONTACT_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(Contact, cid, values, NOT_FOUND)


@bp.route("/api/contact/<int:cid>", methods=["DELETE"])
def delete_contact(cid):
    return _delete_by_id(Contact, cid, NOT_FOUND)
