"""Порталын тохиргоо (Blueprint) — SINGLETON, нэг л мөр.

Порталын толгой хэсэг, нүүрийн баннер, холбоо барих мэдээлэл, хаяг/газрын зураг
өмнө нь portal.html дотор хатуу бичигдсэн байсныг админаас удирдах боломжтой болгов.
Жагсаалт/CRUD хэрэггүй — систем даяар ГАНЦ мөр (id=1) байх тул:

    GET  /api/portal_settings          — админ (portal_settings.read эрх)
    PUT  /api/portal_settings          — бүхэлд нь дарж хадгална (portal_settings.update)
    PATCH /api/portal_settings         — ирсэн талбаруудыг л солино

Токенгүй порталын уншилт (/api/public|portal/portal_settings) нь client/settings.py-д.

Мөр байхгүй бол GET нь core/db.py-ийн DEFAULT_PORTAL_SETTINGS-ээр автоматаар үүсгэнэ —
шинэ орчинд frontend ямар ч өөрчлөлтгүйгээр ажиллана.

Лого: тусдаа endpoint байхгүй — `POST /api/upload` (admin/content.py) руу илгээгээд
буцаж ирсэн `url`-г `logo_url` талбарт хадгална.
"""
import json

from flask import Blueprint, abort, jsonify, request

from core.helpers import json_body, now_str
from core.orm import session
from core.settings_core import SETTINGS_FIELDS, get_row, load_phones, public
from admin.content import remove_upload

bp = Blueprint("portal_settings", __name__)

# URL хэлбэрээр шалгагдах талбарууд (хоосон байж болно)
URL_FIELDS = ("facebook_url", "youtube_url", "map_embed_url")

MAX_TEXT = 2000                 # урт текстийн санал болгосон дээд хэмжээ (спекийн 6)


def _validate(data, partial):
    """Ирсэн утгуудыг шалгаад хадгалах хэлбэрт нь буцаана ({багана: утга})."""
    out = {}
    for f in SETTINGS_FIELDS:
        if f not in data:
            continue
        value = data[f]
        if f == "phones":
            if not isinstance(value, list):
                abort(400, description="phones нь жагсаалт байх ёстой")
            phones = [str(p).strip() for p in value if str(p).strip()]
            if not phones:
                abort(400, description="Дор хаяж нэг утасны дугаар шаардлагатай")
            out[f] = json.dumps(phones, ensure_ascii=False)
            continue
        if value is None:
            out[f] = None
            continue
        if not isinstance(value, str):
            abort(400, description=f"{f} нь текст байх ёстой")
        value = value.strip()
        if len(value) > MAX_TEXT:
            abort(400, description=f"{f} нь {MAX_TEXT} тэмдэгтээс хэтрэхгүй")
        if f in URL_FIELDS and value and not value.startswith(("http://", "https://")):
            abort(400, description=f"{f} нь http:// эсвэл https://-ээр эхлэх ёстой")
        # Газрын зураг iframe-ийн src-д шууд ордог тул зөвхөн Google Maps embed.
        if f == "map_embed_url" and value and "google.com/maps/embed" not in value:
            abort(400, description="map_embed_url нь Google Maps-ийн embed холбоос байх ёстой")
        out[f] = value or None
    if not out:
        abort(400, description="Хадгалах талбар алга. Сонголт: " + ", ".join(SETTINGS_FIELDS))
    # PUT нь бүхэлд нь дарж хадгална — өгөөгүй талбарууд хоосорно (frontend бүх
    # талбараа мэддэг). PATCH бол ирсэн талбаруудыг л солино.
    if not partial:
        for f in SETTINGS_FIELDS:
            out.setdefault(f, None)
        if not load_phones(out["phones"]):
            abort(400, description="Дор хаяж нэг утасны дугаар шаардлагатай")
    return out


# ============================ Маршрутууд ============================
@bp.route("/api/portal_settings", methods=["GET"])
def get_settings():
    """Одоогийн тохиргоо (мөр байхгүй бол анхдагчаар үүсгэж буцаана)."""
    return jsonify(public(get_row()))


@bp.route("/api/portal_settings", methods=["PUT", "PATCH"])
def update_settings():
    """PUT — бүхэлд нь дарж хадгална; PATCH — ирсэн талбаруудыг л солино."""
    data = json_body()
    row = get_row()
    values = _validate(data, partial=request.method == "PATCH")
    old_logo = row.logo_url
    for f, v in {**values, "updated_at": now_str()}.items():
        setattr(row, f, v)
    session().commit()
    out = public(row)
    # Лого солигдвол хуучныг дискнээс арилгана (гадаад URL-д хүрэхгүй).
    if "logo_url" in values and old_logo != values["logo_url"]:
        remove_upload(old_logo)
    return jsonify(out)
