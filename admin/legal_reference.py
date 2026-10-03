"""Эрх зүй — дугаарласан мод, АДМИН тал (Blueprint). Эрх: legal_reference.*

    GET    /api/legal_reference            — бүх мөр (нуусан ч), хавтгай, parent_id-тай
                                             (frontend модыг өөрөө угсарна — /api/menu шиг)
    GET    /api/legal_reference/<id>
    POST   /api/legal_reference            — {parent_id, title, url, sort_order, is_visible}
                                             sort_order өгөхгүй бол ах дүүсийн төгсгөлд
    PUT|PATCH /api/legal_reference/<id>    — хэсэгчилсэн засвар
    DELETE /api/legal_reference/<id>       — дэд мод БҮХЭЛДЭЭ хамт устна (каскад, soft)
    PUT|PATCH /api/legal_reference/reorder — {items: [{id, sort_order}]}; бүгд нэг эцэгтэй

Токенгүй порталын уншилт client/legal.py-д, шалгалт core/legal_ref_core.py-д.
"""
from flask import Blueprint, abort, jsonify
from sqlalchemy import select

from core.helpers import json_body, list_json
from core.legal_ref_core import NOT_FOUND, admin_row, bad, validate
from core.orm import session
from core.orm.models import LegalReference
from core.orm.query import paginate

bp = Blueprint("legal_reference", __name__)


def _obj(rid):
    obj = session().get(LegalReference, rid)
    if obj is None:
        abort(404, description=NOT_FOUND)
    return obj


@bp.route("/api/legal_reference", methods=["GET"])
def list_references():
    items, meta = paginate(select(LegalReference).order_by(
        LegalReference.parent_id.nulls_first(), LegalReference.sort_order, LegalReference.id))
    return list_json([admin_row(o) for o in items], meta)


@bp.route("/api/legal_reference/<int:rid>", methods=["GET"])
def get_reference(rid):
    return jsonify(admin_row(_obj(rid)))


@bp.route("/api/legal_reference", methods=["POST"])
def create_reference():
    s = session()
    obj = LegalReference(**validate(json_body()))
    s.add(obj)
    s.commit()
    return jsonify(admin_row(obj)), 201


@bp.route("/api/legal_reference/reorder", methods=["PUT", "PATCH"])
def reorder_references():
    """Нэг эцгийн доорх ах дүүсийн эрэмбийг хадгална."""
    items = json_body().get("items")
    if not isinstance(items, list) or not items:
        bad("items (жагсаалт) шаардлагатай")
    s = session()
    rows = []
    for item in items:
        if (not isinstance(item, dict) or not str(item.get("id", "")).isdigit()
                or not str(item.get("sort_order", "")).lstrip("-").isdigit()):
            bad("items доторх бичлэг бүр id, sort_order (бүхэл тоо)-той байна")
        obj = s.get(LegalReference, int(item["id"]))
        if obj is None:
            abort(404, description=f"{NOT_FOUND}: {item['id']}")
        rows.append((obj, int(item["sort_order"])))
    if len({obj.parent_id for obj, _ in rows}) > 1:
        bad("items-ийн мөрүүд бүгд нэг эцэгтэй (parent_id) байх ёстой")
    for obj, order in rows:
        obj.sort_order = order
    s.commit()
    return jsonify([admin_row(obj) for obj, _ in sorted(rows, key=lambda r: (r[1], r[0].id))])


@bp.route("/api/legal_reference/<int:rid>", methods=["PUT", "PATCH"])
def update_reference(rid):
    data = json_body()
    obj = _obj(rid)
    values = validate(data, obj.to_dict())
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    for k, v in values.items():
        setattr(obj, k, v)
    session().commit()
    return jsonify(admin_row(obj))


@bp.route("/api/legal_reference/<int:rid>", methods=["DELETE"])
def delete_reference(rid):
    s = session()
    s.delete(_obj(rid))                      # дэд мөрүүд каскадаар (soft delete)
    s.commit()
    return jsonify(deleted=rid)
