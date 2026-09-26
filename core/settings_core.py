"""Порталын тохиргооны (portal_settings) домэйний цөм — хоёр site хуваалцана.

admin/settings.py (GET/PUT/PATCH /api/portal_settings — токен + эрх) болон
client/settings.py (GET /api/public|portal/portal_settings — токенгүй) хоёулаа
эндээс мөрөө уншиж, JSON хэлбэрт оруулна. Систем даяар ГАНЦ мөр байна.
"""
import json

from core.db import DEFAULT_PORTAL_SETTINGS
from core.helpers import insert_row
from core.helpers import now_str

# Хадгалагдах талбарууд (id, огноо нь сервер талынх). phones нь JSON текстээр
# хадгалагдаж, JSON хариунд ҮРГЭЛЖ жагсаалт болж буцна.
SETTINGS_FIELDS = (
    "logo_url", "header_title", "header_subtitle",
    "hero_badge", "hero_title", "hero_text",
    "phones", "website", "facebook_url", "youtube_url",
    "address", "map_embed_url",
)


def public(row):
    """Мөрийг JSON болгоно — phones нь үргэлж жагсаалт."""
    out = {f: row[f] for f in SETTINGS_FIELDS}
    out["phones"] = load_phones(row["phones"])
    out["updated_at"] = row["updated_at"]
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


def get_row(conn):
    """Ганц мөрийг авна; байхгүй бол анхдагч утгуудаар үүсгээд буцаана."""
    row = conn.execute(
        "SELECT * FROM portal_settings ORDER BY id LIMIT 1").fetchone()
    if row:
        return row
    now = now_str()
    values = {f: DEFAULT_PORTAL_SETTINGS[f] for f in SETTINGS_FIELDS}
    values["phones"] = json.dumps(values["phones"], ensure_ascii=False)
    new_id = insert_row(conn, "portal_settings",
                        {**values, "created_at": now, "updated_at": now})
    conn.commit()
    return conn.execute(
        "SELECT * FROM portal_settings WHERE id=?", (new_id,)).fetchone()
