"""Порталын нүүр хуудас — баннер ба хамтрагч байгууллага, ПОРТАЛ тал (Blueprint, токенгүй).

    GET /api/portal/banners   — is_visible, одоо starts_at..ends_at цонхонд (NULL = хязгааргүй)
                                {items: [{id, title, image_url, link_url}]}
    GET /api/portal/partners  — is_visible
                                {items: [{id, name, url, icon}]}

Хоосон жагсаалт ирвэл портал тухайн хэсгийг нууна. Нүүр хуудсанд байнга дуудагддаг тул
5 минутын Cache-Control толгой нэмнэ. /api/portal/ нь auth.py-ийн PUBLIC_PREFIXES-д бий.
"""
from flask import Blueprint, jsonify
from sqlalchemy import or_, select

from core.helpers import now_str
from core.home_core import public_banner, public_partner
from core.orm import session
from core.orm.models import Banner, Partner

bp = Blueprint("portal_home", __name__)

CACHE_SECONDS = 300


def _cached(items):
    resp = jsonify(items=items)
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return resp


@bp.route("/api/portal/banners", methods=["GET"])
def public_banners():
    now = now_str()
    rows = session().scalars(
        select(Banner).where(Banner.is_visible == 1,
                             or_(Banner.starts_at.is_(None), Banner.starts_at <= now),
                             or_(Banner.ends_at.is_(None), Banner.ends_at >= now))
        .order_by(Banner.sort_order, Banner.id))
    return _cached([public_banner(b.to_dict()) for b in rows])


@bp.route("/api/portal/partners", methods=["GET"])
def public_partners():
    rows = session().scalars(select(Partner).where(Partner.is_visible == 1)
                             .order_by(Partner.sort_order, Partner.id))
    return _cached([public_partner(p.to_dict()) for p in rows])
