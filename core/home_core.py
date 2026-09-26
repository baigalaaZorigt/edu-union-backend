"""Порталын нүүр хуудасны баннер / хамтрагч байгууллагын домэйний цөм (хоёр site хуваалцана).

admin/home.py (CRUD — /api/banner, /api/partner, токен + эрх) болон client/home.py
(/api/portal/banners|partners — токенгүй) хоёулаа эндээс талбар, шалгалт, хэлбэржүүлэлтийг авна.

Огноо: starts_at / ends_at нь UTC "YYYY-MM-DD HH:MM:SS" болж хадгалагдана (now_str()-тэй
текстээр харьцуулагдана). Цагийн бүстэй ISO ("...Z", "+08:00") ирвэл UTC руу хөрвүүлнэ;
бүсгүй утгыг UTC гэж үзнэ (мэдэгдлийн scheduled_at-тай ижил).
"""
import re
from datetime import datetime, timezone

from core.helpers import fail

BANNER_FIELDS = ("title", "image_url", "link_url", "sort_order", "is_visible",
                 "starts_at", "ends_at")
PARTNER_FIELDS = ("name", "url", "icon", "sort_order", "is_visible")

MAX_TEXT = 500                 # нэр / гарчиг / URL-ийн дээд урт
MAX_ICON = 16                  # нэг emoji (ZWJ дараалал хэд хэдэн тэмдэгт болдог)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


def _text(conn, value, field, required=False, max_len=MAX_TEXT):
    """Текст талбар: хоосон -> None (required бол 400), урт/төрлийг шалгана."""
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            fail(conn, 400, f"{field} заавал шаардлагатай")
        return None
    if not isinstance(value, str):
        fail(conn, 400, f"{field} нь текст байх ёстой")
    value = value.strip()
    if len(value) > max_len:
        fail(conn, 400, f"{field} хэт урт (дээд тал нь {max_len} тэмдэгт)")
    return value


def _http(value):
    return value.lower().startswith(("http://", "https://"))


def _link(conn, value, field, required=False):
    """http(s):// эсвэл харьцангуй зам ("/uploads/...", "news/5"); бусад схем (javascript: г.м.)
    болон "//host" хэлбэрийг хүлээж авахгүй."""
    value = _text(conn, value, field, required)
    if value is None or _http(value):
        return value
    if _SCHEME.match(value) or value.startswith("//"):
        fail(conn, 400, f"{field} нь http(s):// эсвэл харьцангуй зам байх ёстой")
    return value


def _int(conn, value, field):
    if isinstance(value, bool):
        fail(conn, 400, f"{field} нь бүхэл тоо байх ёстой")
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(conn, 400, f"{field} нь бүхэл тоо байх ёстой")


def _flag(conn, value, field):
    """true/false, 1/0, "true"/"false" -> 1/0."""
    if value in (True, 1, "1", "true", "True"):
        return 1
    if value in (False, 0, "0", "false", "False"):
        return 0
    fail(conn, 400, f"{field} нь true/false байх ёстой")


def _when(conn, value, field):
    """ISO огноо/цаг -> UTC "YYYY-MM-DD HH:MM:SS" (хоосон -> None)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        fail(conn, 400, f"{field} нь текст огноо байх ёстой")
    raw = value.strip().replace(" ", "T", 1)
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        fail(conn, 400, f"{field} буруу огноо (ж: 2026-10-01 09:00:00 эсвэл ISO 8601)")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def validate_banner(conn, data, current=None):
    """Ирсэн талбаруудыг шалгаж хадгалах утгуудыг буцаана.

    current (засах үед одоогийн мөр) — хэсэгчилсэн PUT/PATCH-ийн дараах НИЙЛМЭЛ төлөвөөр
    image_url заавал эсэх, starts_at <= ends_at-ийг шалгана.
    """
    out = {}
    if "title" in data:
        out["title"] = _text(conn, data["title"], "title")
    if "image_url" in data or current is None:
        out["image_url"] = _link(conn, data.get("image_url"), "image_url", required=True)
    if "link_url" in data:
        out["link_url"] = _link(conn, data["link_url"], "link_url")
    if "sort_order" in data:
        out["sort_order"] = _int(conn, data["sort_order"], "sort_order")
    if "is_visible" in data:
        out["is_visible"] = _flag(conn, data["is_visible"], "is_visible")
    for f in ("starts_at", "ends_at"):
        if f in data:
            out[f] = _when(conn, data[f], f)
    merged = {**(dict(current) if current else {}), **out}
    if merged.get("starts_at") and merged.get("ends_at") \
            and merged["ends_at"] < merged["starts_at"]:
        fail(conn, 400, "ends_at нь starts_at-аас өмнө байж болохгүй")
    return out


def validate_partner(conn, data, current=None):
    """Хамтрагч байгууллагын талбаруудыг шалгана (name, url заавал; url нь http(s)://)."""
    out = {}
    if "name" in data or current is None:
        out["name"] = _text(conn, data.get("name"), "name", required=True)
    if "url" in data or current is None:
        url = _text(conn, data.get("url"), "url", required=True)
        if not _http(url):
            fail(conn, 400, "url нь http:// эсвэл https://-ээр эхлэх ёстой")
        out["url"] = url
    if "icon" in data:
        out["icon"] = _text(conn, data["icon"], "icon", max_len=MAX_ICON)
    if "sort_order" in data:
        out["sort_order"] = _int(conn, data["sort_order"], "sort_order")
    if "is_visible" in data:
        out["is_visible"] = _flag(conn, data["is_visible"], "is_visible")
    return out


def admin_row(row):
    """Админ хариу: бүх багана, is_visible нь bool."""
    out = dict(row)
    out["is_visible"] = bool(out["is_visible"])
    return out


def public_banner(row):
    return {k: row[k] for k in ("id", "title", "image_url", "link_url")}


def public_partner(row):
    return {k: row[k] for k in ("id", "name", "url", "icon")}
