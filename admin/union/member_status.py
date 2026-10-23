"""member_status (Гишүүний статус, лавлах) — Гишүүн, Дарга, Тэргүүлэгч ...

member.status_id эндээс сонгоно; хуучин member.status текст нь нэрийг нь давтана.
CRUD нь бусад кодтой лавлахынхтай ижил (references.py-ийн туслахууд), нэр нь мөн давтагдашгүй.
"""
from admin.union import bp
from admin.union.references import _ref_create, _ref_delete, _ref_get, _ref_list, _ref_update

LABEL = "Гишүүний статус"


@bp.route("/api/member_status", methods=["GET"])
def list_member_status():
    return _ref_list("member_status")


@bp.route("/api/member_status/<int:sid>", methods=["GET"])
def get_member_status(sid):
    return _ref_get("member_status", sid, LABEL)


@bp.route("/api/member_status", methods=["POST"])
def create_member_status():
    return _ref_create("member_status", LABEL)


@bp.route("/api/member_status/<int:sid>", methods=["PUT", "PATCH"])
def update_member_status(sid):
    return _ref_update("member_status", sid, LABEL)


@bp.route("/api/member_status/<int:sid>", methods=["DELETE"])
def delete_member_status(sid):
    return _ref_delete("member_status", sid, LABEL)
