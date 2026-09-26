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

from flask import Blueprint, jsonify, request

from core.db import get_db
from core.helpers import json_body, fail, update_row
from core.helpers import now_str
from core.settings_core import SETTINGS_FIELDS, get_row, load_phones, public
from admin.content import remove_upload

bp = Blueprint("portal_settings", __name__)

# URL хэлбэрээр шалгагдах талбарууд (хоосон байж болно)
URL_FIELDS = ("facebook_url", "youtube_url", "map_embed_url")

MAX_TEXT = 2000                 # урт текстийн санал болгосон дээд хэмжээ (спекийн 6)


def _validate(conn, data, partial):
    """Ирсэн утгуудыг шалгаад хадгалах хэлбэрт нь буцаана ({багана: утга})."""
    out = {}
    for f in SETTINGS_FIELDS:
        if f not in data:
            continue
        value = data[f]
        if f == "phones":
            if not isinstance(value, list):
                fail(conn, 400, "phones нь жагсаалт байх ёстой")
            phones = [str(p).strip() for p in value if str(p).strip()]
            if not phones:
                fail(conn, 400, "Дор хаяж нэг утасны дугаар шаардлагатай")
            out[f] = json.dumps(phones, ensure_ascii=False)
            continue
        if value is None:
            out[f] = None
            continue
        if not isinstance(value, str):
            fail(conn, 400, f"{f} нь текст байх ёстой")
        value = value.strip()
        if len(value) > MAX_TEXT:
            fail(conn, 400, f"{f} нь {MAX_TEXT} тэмдэгтээс хэтрэхгүй")
        if f in URL_FIELDS and value and not value.startswith(("http://", "https://")):
            fail(conn, 400, f"{f} нь http:// эсвэл https://-ээр эхлэх ёстой")
        # Газрын зураг iframe-ийн src-д шууд ордог тул зөвхөн Google Maps embed.
        if f == "map_embed_url" and value and "google.com/maps/embed" not in value:
            fail(conn, 400, "map_embed_url нь Google Maps-ийн embed холбоос байх ёстой")
        out[f] = value or None
    if not out:
        fail(conn, 400, "Хадгалах талбар алга. Сонголт: " + ", ".join(SETTINGS_FIELDS))
    # PUT нь бүхэлд нь дарж хадгална — өгөөгүй талбарууд хоосорно (frontend бүх
    # талбараа мэддэг). PATCH бол ирсэн талбаруудыг л солино.
    if not partial:
        for f in SETTINGS_FIELDS:
            out.setdefault(f, None)
        if not load_phones(out["phones"]):
            fail(conn, 400, "Дор хаяж нэг утасны дугаар шаардлагатай")
    return out


# ============================ Маршрутууд ============================
@bp.route("/api/portal_settings", methods=["GET"])
def get_settings():
    """Одоогийн тохиргоо (мөр байхгүй бол анхдагчаар үүсгэж буцаана)."""
    conn = get_db()
    out = public(get_row(conn))
    conn.close()
    return jsonify(out)


@bp.route("/api/portal_settings", methods=["PUT", "PATCH"])
def update_settings():
    """PUT — бүхэлд нь дарж хадгална; PATCH — ирсэн талбаруудыг л солино."""
    data = json_body()
    conn = get_db()
    current = get_row(conn)
    values = _validate(conn, data, partial=request.method == "PATCH")
    update_row(conn, "portal_settings", current["id"],
               {**values, "updated_at": now_str()})
    conn.commit()
    row = conn.execute(
        "SELECT * FROM portal_settings WHERE id=?", (current["id"],)).fetchone()
    out = public(row)
    conn.close()
    # Лого солигдвол хуучныг дискнээс арилгана (гадаад URL-д хүрэхгүй).
    if "logo_url" in values and current["logo_url"] != values["logo_url"]:
        remove_upload(current["logo_url"])
    return jsonify(out)
