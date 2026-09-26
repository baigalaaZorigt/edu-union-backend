"""Порталын нүүр хуудас — баннер ба хамтрагч байгууллага, ПОРТАЛ тал (Blueprint, токенгүй).

    GET /api/portal/banners   — is_visible, одоо starts_at..ends_at цонхонд (NULL = хязгааргүй)
                                {items: [{id, title, image_url, link_url}]}
    GET /api/portal/partners  — is_visible
                                {items: [{id, name, url, icon}]}

Хоосон жагсаалт ирвэл портал тухайн хэсгийг нууна. Нүүр хуудсанд байнга дуудагддаг тул
5 минутын Cache-Control толгой нэмнэ. /api/portal/ нь auth.py-ийн PUBLIC_PREFIXES-д бий.
"""
from flask import Blueprint, jsonify

from core.db import get_db
from core.helpers import now_str
from core.home_core import public_banner, public_partner

bp = Blueprint("portal_home", __name__)

CACHE_SECONDS = 300


def _cached(items):
    resp = jsonify(items=items)
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return resp


@bp.route("/api/portal/banners", methods=["GET"])
def public_banners():
    now = now_str()
    conn = get_db()
    data = [public_banner(r) for r in conn.execute(
        "SELECT * FROM banner WHERE is_visible=1 "
        "AND (starts_at IS NULL OR starts_at <= ?) AND (ends_at IS NULL OR ends_at >= ?) "
        "ORDER BY sort_order, id", (now, now)).fetchall()]
    conn.close()
    return _cached(data)


@bp.route("/api/portal/partners", methods=["GET"])
def public_partners():
    conn = get_db()
    data = [public_partner(r) for r in conn.execute(
        "SELECT * FROM partner WHERE is_visible=1 ORDER BY sort_order, id").fetchall()]
    conn.close()
    return _cached(data)
