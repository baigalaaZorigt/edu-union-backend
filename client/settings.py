"""Порталын тохиргооны ПОРТАЛ тал (Blueprint) — зөвхөн унших, токенгүй.

    GET  /api/public/portal_settings   — порталын толгой/баннер/холбоо барих
    GET  /api/portal/portal_settings   — мөн адил (одоо байгаа /api/portal/... хэв маяг)

Хоёр угтвар хоёулаа core/auth.py-ийн PUBLIC_PREFIXES-д байгаа тул токен шаардахгүй.
Засах нь admin/settings.py-д (токен + portal_settings.update эрх).
"""
from flask import Blueprint, jsonify

from core.settings_core import get_row, public

bp = Blueprint("public_settings", __name__)


@bp.route("/api/public/portal_settings", methods=["GET"])
@bp.route("/api/portal/portal_settings", methods=["GET"])
def public_settings():
    """Одоогийн тохиргоо (мөр байхгүй бол анхдагчаар үүсгэж буцаана)."""
    return jsonify(public(get_row()))
