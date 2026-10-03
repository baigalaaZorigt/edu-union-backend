"""Порталын тохиргооны (portal_settings) домэйний цөм — хоёр site хуваалцана.

admin/settings.py (GET/PUT/PATCH /api/portal_settings — токен + эрх) болон
client/settings.py (GET /api/public|portal/portal_settings — токенгүй) хоёулаа
эндээс мөрөө уншиж, JSON хэлбэрт оруулна. Систем даяар ГАНЦ мөр байна.
"""
import json

from sqlalchemy import select

from core.db import DEFAULT_PORTAL_SETTINGS
from core.helpers import now_str
from core.orm import session
from core.orm.models import PortalSettings

# Хадгалагдах талбарууд (id, огноо нь сервер талынх). phones нь JSON текстээр
# хадгалагдаж, JSON хариунд ҮРГЭЛЖ жагсаалт болж буцна.
SETTINGS_FIELDS = (
    "logo_url", "header_title", "header_subtitle",
    "hero_badge", "hero_title", "hero_text",
    "phones", "website", "facebook_url", "youtube_url",
    "address", "map_embed_url",
)


def public(row, audit=False):
    """Мөрийг (PortalSettings) JSON болгоно — phones нь үргэлж жагсаалт; audit=True (админ)
    -> created_by/updated_by."""
    out = {f: getattr(row, f) for f in SETTINGS_FIELDS}
    out["phones"] = load_phones(row.phones)
    out["updated_at"] = row.updated_at
    if audit:
        out.update(created_by=row.created_by, updated_by=row.updated_by)
    return out


def load_phones(raw):
    """JSON текстээс утасны жагсаалт гаргана (эвдэрсэн бол хоосон жагсаалт)."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def get_row():
    """Ганц мөрийг (PortalSettings) авна; байхгүй бол анхдагч утгуудаар үүсгээд буцаана."""
    s = session()
    row = s.scalar(select(PortalSettings).order_by(PortalSettings.id).limit(1))
    if row is not None:
        return row
    now = now_str()
    values = {f: DEFAULT_PORTAL_SETTINGS[f] for f in SETTINGS_FIELDS}
    values["phones"] = json.dumps(values["phones"], ensure_ascii=False)
    row = PortalSettings(**values, created_at=now, updated_at=now)
    s.add(row)
    s.commit()
    return row
