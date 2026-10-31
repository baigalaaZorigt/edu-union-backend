"""Нүүр хуудасны «Холбооны тухай» хэсгийн домэйний цөм (хоёр site хуваалцана).

admin/home_about.py (/api/admin/home_about... — токен + home_about.* эрх) болон client/home.py
(/api/portal/home_about — токенгүй) хоёулаа эндээс шалгалт, хэлбэржүүлэлтийг авна.
backend-spec-home-about.md-ийг хэрэгжүүлнэ.

Алдаа: спекийн дагуу 422 + талбар тус бүрийн мессеж — {"error": "...", "errors": {"title": ...}}
(репогийн бусад хэсэг 400 буцаадаг; энэ хэсгийг шинэ админ UI талбар бүрт нь харуулна).
Текст ТЕКСТ хэвээр хадгалагдана: HTML tag-ийг хадгалахаас өмнө хасна (портал markup рендерлэхгүй).
"""
import re

from flask import abort
from werkzeug.exceptions import UnprocessableEntity

from core.orm.models.home import HomeAbout

SINGLETON_ID = 1
DEFAULT_TITLE = "Холбооны тухай"
MAX_TITLE = 120
MAX_BODY = 1500
MAX_CARD_TITLE = 60
MAX_CARD_TEXT = 300
MAX_CARDS = 6                  # хадгалах дээд тоо
MAX_PUBLIC_CARDS = 4           # порталд буцаах дээд тоо (дизайн 3, дээд тал 4)

_TAG = re.compile(r"<[^>]*>")


class Invalid(UnprocessableEntity):
    """422 — `extra` нь {"errors": {талбар: мессеж}} (core.helpers.register_error_handlers)."""

    def __init__(self, errors):
        super().__init__(description="; ".join(errors.values()))
        self.extra = {"errors": errors}


def strip_html(value):
    prev = None
    while prev != value:                       # "<<b>script>" мэт давхар tag-ийг ч арилгана
        prev, value = value, _TAG.sub("", value)
    return value


def _text(data, field, errors, max_len, min_len=1, label=None):
    value = data.get(field)
    if value is None:
        value = ""
    if not isinstance(value, str):
        errors[field] = f"{label or field} нь текст байх ёстой"
        return None
    value = strip_html(value).strip()
    if len(value) < min_len:
        errors[field] = f"{label or field} заавал бөглөнө"
    elif len(value) > max_len:
        errors[field] = f"{label or field} хэт урт (дээд тал нь {max_len} тэмдэгт)"
    return value


def clean_body(value):
    """Мөрийн төгсгөл -> \\n, хоосон зайтай мөр -> хоосон, 3+ шинэ мөр -> 2 (догол мөрийн зааг)."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def _flag(value, field, errors):
    if value in (True, 1, "1", "true", "True"):
        return 1
    if value in (False, 0, "0", "false", "False"):
        return 0
    errors[field] = f"{field} нь true/false байх ёстой"
    return None


def validate_about(data):
    """PUT|PATCH /api/admin/home_about — ирсэн title / body-г шалгана (хэсэгчилсэн)."""
    out, errors = {}, {}
    if "title" in data:
        out["title"] = _text(data, "title", errors, MAX_TITLE, label="Гарчиг")
    if "body" in data:
        body = data["body"]
        if body is not None and not isinstance(body, str):
            errors["body"] = "Үндсэн текст нь текст байх ёстой"
        else:
            out["body"] = clean_body(strip_html(body or ""))
            if len(out["body"]) > MAX_BODY:
                errors["body"] = f"Үндсэн текст хэт урт (дээд тал нь {MAX_BODY} тэмдэгт)"
    if errors:
        raise Invalid(errors)
    if not out:
        abort(400, description="Шинэчлэх талбар алга (title, body)")
    return out


def validate_card(data, partial=False):
    """Карт: title (1–60), text (1–300) заавал (засахад зөвхөн ирсэн нь), is_visible bool."""
    out, errors = {}, {}
    if "title" in data or not partial:
        out["title"] = _text(data, "title", errors, MAX_CARD_TITLE, label="Гарчиг")
    if "text" in data or not partial:
        out["text"] = _text(data, "text", errors, MAX_CARD_TEXT, label="Текст")
    if "is_visible" in data:
        out["is_visible"] = _flag(data["is_visible"], "is_visible", errors)
    if errors:
        raise Invalid(errors)
    if not out:
        abort(400, description="Шинэчлэх талбар алга (title, text, is_visible)")
    return out


def get_about(s, create=False):
    """Singleton мөр; байхгүй бол None (create=True бол анхдагчаар үүсгэнэ)."""
    row = s.get(HomeAbout, SINGLETON_ID)
    if row is None and create:
        row = HomeAbout(id=SINGLETON_ID, title=DEFAULT_TITLE, body="")
        s.add(row)
    return row


def admin_card(card):
    out = card.to_dict()
    out["is_visible"] = bool(out["is_visible"])
    return out


def public_card(card):
    return {"id": card.id, "title": card.title, "text": card.text}


def iso_z(value):
    """"2026-10-31T09:00:00+00:00" / "2026-10-31 09:00:00" -> "2026-10-31T09:00:00Z"."""
    if not value:
        return None
    value = value.replace(" ", "T", 1)
    return value[:-6] + "Z" if value.endswith("+00:00") else value
