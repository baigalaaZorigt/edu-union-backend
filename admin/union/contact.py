"""contact (Холбоо барих) — хороо/байгууллага/гишүүнд полиморфоор харьяалагдана."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import insert_row, json_body, pick, require

from admin.union import bp
from admin.union.common import _delete_by_id, _list_rows, _require_row, _update_by_id


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
    if owner_type and owner_id:
        return _list_rows(
            "SELECT * FROM contact WHERE owner_type=? AND owner_id=? ORDER BY id",
            (owner_type, owner_id))
    return _list_rows("SELECT * FROM contact ORDER BY id")


@bp.route("/api/contact", methods=["POST"])
def create_contact():
    data = request.get_json(silent=True)
    require(data, ["owner_type", "owner_id", "type", "value"])
    if data["owner_type"] not in OWNER_TYPES:
        abort(400, description="owner_type буруу. Сонголт: " + ", ".join(OWNER_TYPES))
    if data["type"] not in CONTACT_TYPES:
        _bad_type()
    conn = get_db()
    # owner_type нь хүснэгтийн нэртэй ижил
    _require_row(conn, data["owner_type"], data["owner_id"], "Эзэмшигч (owner_id) олдсонгүй")
    new_id = insert_row(conn, "contact", {
        "owner_type": data["owner_type"], "owner_id": data["owner_id"],
        "type": data["type"], "value": data["value"], "note": data.get("note")})
    conn.commit()
    conn.close()
    return jsonify(id=new_id, **data), 201


@bp.route("/api/contact/<int:cid>", methods=["PUT", "PATCH"])
def update_contact(cid):
    data = json_body()
    if data.get("type") and data["type"] not in CONTACT_TYPES:
        _bad_type()
    values = pick(data, CONTACT_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    return _update_by_id(get_db(), "contact", cid, values, NOT_FOUND)


@bp.route("/api/contact/<int:cid>", methods=["DELETE"])
def delete_contact(cid):
    return _delete_by_id(get_db(), "contact", cid, NOT_FOUND)
