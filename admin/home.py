"""Порталын нүүр хуудас — баннер ба хамтрагч байгууллага, АДМИН тал (Blueprint).

    GET    /api/banner              — бүх мөр (нуусан, хугацаа дууссан ч), sort_order, id
    GET    /api/banner/<id>
    POST   /api/banner              — {title, image_url, link_url, sort_order, is_visible,
                                       starts_at, ends_at}; image_url заавал
    PUT|PATCH /api/banner/<id>      — хэсэгчилсэн засвар
    DELETE /api/banner/<id>         — зураг нь /uploads/content/ дотор бол дискнээс ч арилна
    ... /api/partner                — ижил бүтэц: {name, url, icon, logo_url, sort_order,
                                       is_visible}; лого солигдох/устгахад файл нь арилна

Эрх: banner.* / partner.* (auth.py замын эхний сегментээс автоматаар гаргана).
Токенгүй порталын уншилт нь client/home.py-д. Шалгалт core/home_core.py-д.
"""
from flask import Blueprint, abort, jsonify
from sqlalchemy import select

from core.helpers import json_body, list_json
from core.home_core import admin_row, validate_banner, validate_partner
from core.orm import session
from core.orm.models import Banner, Partner
from core.orm.query import paginate
from admin.content import remove_upload

bp = Blueprint("home_content", __name__)

MODELS = {"banner": Banner, "partner": Partner}
NOT_FOUND = {"banner": "Баннер олдсонгүй", "partner": "Хамтрагч байгууллага олдсонгүй"}
VALIDATE = {"banner": validate_banner, "partner": validate_partner}
IMAGE_FIELD = {"banner": "image_url", "partner": "logo_url"}   # солих/устгахад файлыг арилгана


def _obj(table, rid):
    obj = session().get(MODELS[table], rid)
    if obj is None:
        abort(404, description=NOT_FOUND[table])
    return obj


def _list(table):
    model = MODELS[table]
    items, meta = paginate(select(model).order_by(model.sort_order, model.id))
    return list_json([admin_row(o.to_dict()) for o in items], meta)


def _get(table, rid):
    return jsonify(admin_row(_obj(table, rid).to_dict()))


def _create(table):
    data = json_body()
    s = session()
    obj = MODELS[table](**VALIDATE[table](data))
    s.add(obj)
    s.commit()
    return jsonify(admin_row(obj.to_dict())), 201


def _update(table, rid):
    data = json_body()
    s = session()
    obj = _obj(table, rid)
    current = obj.to_dict()
    values = VALIDATE[table](data, current)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    for k, v in values.items():
        setattr(obj, k, v)
    s.commit()
    out = admin_row(obj.to_dict())
    # Зураг (баннер / лого) солигдвол хуучныг сангаас арилгана (гадаад URL-д хүрэхгүй).
    field = IMAGE_FIELD[table]
    if field in values and values[field] != current[field]:
        remove_upload(current[field])
    return jsonify(out)


def _delete(table, rid):
    s = session()
    obj = _obj(table, rid)
    image = getattr(obj, IMAGE_FIELD[table])
    s.delete(obj)
    s.commit()
    remove_upload(image)
    return jsonify(deleted=rid)


def _register(table):
    """/api/<table> CRUD маршрутуудыг бүртгэнэ (endpoint: list_banner, create_partner ...)."""
    base = f"/api/{table}"
    bp.add_url_rule(base, f"list_{table}", lambda: _list(table), methods=["GET"])
    bp.add_url_rule(base, f"create_{table}", lambda: _create(table), methods=["POST"])
    bp.add_url_rule(f"{base}/<int:rid>", f"get_{table}",
                    lambda rid: _get(table, rid), methods=["GET"])
    bp.add_url_rule(f"{base}/<int:rid>", f"update_{table}",
                    lambda rid: _update(table, rid), methods=["PUT", "PATCH"])
    bp.add_url_rule(f"{base}/<int:rid>", f"delete_{table}",
                    lambda rid: _delete(table, rid), methods=["DELETE"])


for _table in ("banner", "partner"):
    _register(_table)
