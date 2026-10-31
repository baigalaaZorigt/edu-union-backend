"""Нүүр хуудасны «Холбооны тухай» хэсэг, АДМИН тал (Blueprint) — backend-spec-home-about.md §5.

    GET       /api/admin/home_about                    — {title, body, updated_at, updated_by,
                                                          cards: [бүх карт, нуусан ч]}
    PUT|PATCH /api/admin/home_about                    — {title, body} (хэсэгчилсэн)
    POST      /api/admin/home_about/cards              — {title, text, is_visible}; төгсгөлд нэмнэ
    PUT|PATCH /api/admin/home_about/cards/reorder      — {ids: [3, 1, 2]} — БҮХ картын id
    PUT|PATCH /api/admin/home_about/cards/<id>         — {title, text, is_visible}
    DELETE    /api/admin/home_about/cards/<id>         — soft delete

Эрх: home_about.* (auth.py "admin" сегментийг алгасна; .../reorder -> update).
Шалгалт ба хариуны хэлбэр core/home_about_core.py-д; токенгүй уншилт client/home.py-д.
"""
from flask import Blueprint, abort, jsonify
from sqlalchemy import func, select

from core.helpers import json_body
from core.home_about_core import (
    MAX_CARDS, Invalid, admin_card, get_about, validate_about, validate_card,
)
from core.orm import session
from core.orm.models import HomeAboutCard

bp = Blueprint("admin_home_about", __name__)

BASE = "/api/admin/home_about"


def _cards(s):
    return s.scalars(select(HomeAboutCard)
                     .order_by(HomeAboutCard.sort_order, HomeAboutCard.id)).all()


def _card(s, cid):
    card = s.get(HomeAboutCard, cid)
    if card is None:
        abort(404, description="Карт олдсонгүй")
    return card


def _section(s):
    about = get_about(s)
    return {
        "title": about.title if about else None,
        "body": about.body if about else "",
        "updated_at": about.updated_at if about else None,
        "updated_by": about.updated_by if about else None,
        "cards": [admin_card(c) for c in _cards(s)],
    }


@bp.route(BASE, methods=["GET"])
def get_home_about():
    return jsonify(_section(session()))


@bp.route(BASE, methods=["PUT", "PATCH"])
def update_home_about():
    values = validate_about(json_body())
    s = session()
    about = get_about(s, create=True)
    for k, v in values.items():
        setattr(about, k, v)
    s.commit()
    return jsonify(_section(s))


@bp.route(f"{BASE}/cards", methods=["POST"])
def create_home_about_card():
    values = validate_card(json_body())
    s = session()
    if s.scalar(select(func.count()).select_from(HomeAboutCard)) >= MAX_CARDS:
        raise Invalid({"cards": f"Дээд тал нь {MAX_CARDS} карт хадгална — эхлээд нэгийг устга"})
    last = s.scalar(select(func.max(HomeAboutCard.sort_order)))
    card = HomeAboutCard(**values, sort_order=(last or 0) + 1)
    s.add(card)
    s.commit()
    return jsonify(admin_card(card)), 201


@bp.route(f"{BASE}/cards/reorder", methods=["PUT", "PATCH"])
def reorder_home_about_cards():
    ids = json_body().get("ids")
    s = session()
    cards = {c.id: c for c in _cards(s)}
    if not isinstance(ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in ids):
        raise Invalid({"ids": "ids нь картын id-уудын жагсаалт байх ёстой"})
    if len(ids) != len(set(ids)) or set(ids) != set(cards):
        raise Invalid({"ids": "ids нь бүх картын id-г яг нэг удаа агуулах ёстой"})
    for pos, cid in enumerate(ids, start=1):
        cards[cid].sort_order = pos
    s.commit()
    return jsonify(cards=[admin_card(c) for c in _cards(s)])


@bp.route(f"{BASE}/cards/<int:cid>", methods=["PUT", "PATCH"])
def update_home_about_card(cid):
    values = validate_card(json_body(), partial=True)
    s = session()
    card = _card(s, cid)
    for k, v in values.items():
        setattr(card, k, v)
    s.commit()
    return jsonify(admin_card(card))


@bp.route(f"{BASE}/cards/<int:cid>", methods=["DELETE"])
def delete_home_about_card(cid):
    s = session()
    s.delete(_card(s, cid))                  # soft delete
    s.commit()
    return jsonify(deleted=cid)
