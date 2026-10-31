"""Порталын нүүр хуудас — баннер ба хамтрагч байгууллага, ПОРТАЛ тал (Blueprint, токенгүй).

    GET /api/portal/banners   — is_visible, одоо starts_at..ends_at цонхонд (NULL = хязгааргүй)
                                {items: [{id, title, image_url, link_url}]}
    GET /api/portal/partners  — is_visible
                                {items: [{id, name, url, icon, logo_url}]}
    GET /api/portal/home_about — «Холбооны тухай»: {title, body, cards: [{id, title, text}],
                                updated_at}; харагдах картаас дээд тал нь 4, sort_order-оор.
                                Тохируулаагүй ч 404 биш — body "" ба cards [] (портал өөрийн
                                хатуу текст рүү буцна). backend-spec-home-about.md §4.

Хоосон жагсаалт ирвэл портал тухайн хэсгийг нууна. Нүүр хуудсанд байнга дуудагддаг тул
5 минутын Cache-Control толгой нэмнэ. /api/portal/ нь auth.py-ийн PUBLIC_PREFIXES-д бий.
"""
from flask import Blueprint, jsonify
from sqlalchemy import or_, select

from core.helpers import now_str
from core.home_about_core import DEFAULT_TITLE, MAX_PUBLIC_CARDS, get_about, iso_z, public_card
from core.home_core import public_banner, public_partner
from core.orm import session
from core.orm.models import Banner, HomeAboutCard, Partner

bp = Blueprint("portal_home", __name__)

CACHE_SECONDS = 300


def _cached(items=None, **payload):
    resp = jsonify(items=items) if items is not None else jsonify(payload)
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


@bp.route("/api/portal/home_about", methods=["GET"])
def public_home_about():
    s = session()
    about = get_about(s)
    cards = s.scalars(select(HomeAboutCard).where(HomeAboutCard.is_visible == 1)
                      .order_by(HomeAboutCard.sort_order, HomeAboutCard.id)
                      .limit(MAX_PUBLIC_CARDS)).all()
    stamps = [x.updated_at for x in ([about] if about else []) + cards if x.updated_at]
    return _cached(title=about.title if about else DEFAULT_TITLE,
                   body=about.body if about else "",
                   cards=[public_card(c) for c in cards],
                   updated_at=iso_z(max(stamps)) if stamps else None)
