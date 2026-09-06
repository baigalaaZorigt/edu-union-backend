"""Порталын тохиргоо (Blueprint) — SINGLETON, нэг л мөр.

Порталын толгой хэсэг, нүүрийн баннер, холбоо барих мэдээлэл, хаяг/газрын зураг
өмнө нь portal.html дотор хатуу бичигдсэн байсныг админаас удирдах боломжтой болгов.
Жагсаалт/CRUD хэрэггүй — систем даяар ГАНЦ мөр (id=1) байх тул:

    GET  /api/portal_settings          — админ (portal_settings.read эрх)
    PUT  /api/portal_settings          — бүхэлд нь дарж хадгална (portal_settings.update)
    PATCH /api/portal_settings         — ирсэн талбаруудыг л солино
    GET  /api/public/portal_settings   — ПОРТАЛ, токен шаардахгүй
    GET  /api/portal/portal_settings   — мөн адил (одоо байгаа /api/portal/... хэв маяг)

Мөр байхгүй бол GET нь db.py-ийн DEFAULT_PORTAL_SETTINGS-ээр автоматаар үүсгэнэ —
шинэ орчинд frontend ямар ч өөрчлөлтгүйгээр ажиллана.

Лого: тусдаа endpoint байхгүй — `POST /api/upload` (admin/content.py) руу илгээгээд
буцаж ирсэн `url`-г `logo_url` талбарт хадгална.
"""
import json

from flask import Blueprint, jsonify, request, abort

from db import get_db, DEFAULT_PORTAL_SETTINGS
from helpers import json_body
from admin.content import remove_upload
from news_core import now_str

bp = Blueprint("portal_settings", __name__)

# Хадгалагдах талбарууд (id, огноо нь сервер талынх). phones нь JSON текстээр
# хадгалагдаж, JSON хариунд ҮРГЭЛЖ жагсаалт болж буцна.
SETTINGS_FIELDS = (
    "logo_url", "header_title", "header_subtitle",
    "hero_badge", "hero_title", "hero_text",
    "phones", "website", "facebook_url", "youtube_url",
    "address", "map_embed_url",
)

# URL хэлбэрээр шалгагдах талбарууд (хоосон байж болно)
URL_FIELDS = ("facebook_url", "youtube_url", "map_embed_url")

MAX_TEXT = 2000                 # урт текстийн санал болгосон дээд хэмжээ (спекийн 6)


# ----------------------------- Туслахууд -----------------------------
def _public(row):
    """Мөрийг JSON болгоно — phones нь үргэлж жагсаалт."""
    out = {f: row[f] for f in SETTINGS_FIELDS}
    out["phones"] = _load_phones(row["phones"])
    out["updated_at"] = row["updated_at"]
    return out


def _load_phones(raw):
    """JSON текстээс утасны жагсаалт гаргана (эвдэрсэн бол хоосон жагсаалт)."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _row(conn):
    """Ганц мөрийг авна; байхгүй бол анхдагч утгуудаар үүсгээд буцаана."""
    row = conn.execute(
        "SELECT * FROM portal_settings ORDER BY id LIMIT 1").fetchone()
    if row:
        return row
    d = DEFAULT_PORTAL_SETTINGS
    now = now_str()
    cur = conn.execute(
        "INSERT INTO portal_settings(logo_url, header_title, header_subtitle, "
        "hero_badge, hero_title, hero_text, phones, website, facebook_url, "
        "youtube_url, address, map_embed_url, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (d["logo_url"], d["header_title"], d["header_subtitle"], d["hero_badge"],
         d["hero_title"], d["hero_text"], json.dumps(d["phones"], ensure_ascii=False),
         d["website"], d["facebook_url"], d["youtube_url"], d["address"],
         d["map_embed_url"], now, now))
    conn.commit()
    return conn.execute(
        "SELECT * FROM portal_settings WHERE id=?", (cur.lastrowid,)).fetchone()


def _bad(conn, message):
    conn.close()
    abort(400, description=message)


def _validate(conn, data, partial):
    """Ирсэн утгуудыг шалгаад хадгалах хэлбэрт нь буцаана ({багана: утга})."""
    out = {}
    for f in SETTINGS_FIELDS:
        if f not in data:
            continue
        value = data[f]
        if f == "phones":
            if not isinstance(value, list):
                _bad(conn, "phones нь жагсаалт байх ёстой")
            phones = [str(p).strip() for p in value if str(p).strip()]
            if not phones:
                _bad(conn, "Дор хаяж нэг утасны дугаар шаардлагатай")
            out[f] = json.dumps(phones, ensure_ascii=False)
            continue
        if value is None:
            out[f] = None
            continue
        if not isinstance(value, str):
            _bad(conn, f"{f} нь текст байх ёстой")
        value = value.strip()
        if len(value) > MAX_TEXT:
            _bad(conn, f"{f} нь {MAX_TEXT} тэмдэгтээс хэтрэхгүй")
        if f in URL_FIELDS and value and not value.startswith(("http://", "https://")):
            _bad(conn, f"{f} нь http:// эсвэл https://-ээр эхлэх ёстой")
        # Газрын зураг iframe-ийн src-д шууд ордог тул зөвхөн Google Maps embed.
        if f == "map_embed_url" and value and "google.com/maps/embed" not in value:
            _bad(conn, "map_embed_url нь Google Maps-ийн embed холбоос байх ёстой")
        out[f] = value or None
    if not out:
        _bad(conn, "Хадгалах талбар алга. Сонголт: " + ", ".join(SETTINGS_FIELDS))
    # PUT нь бүхэлд нь дарж хадгална — өгөөгүй талбарууд хоосорно (frontend бүх
    # талбараа мэддэг). PATCH бол ирсэн талбаруудыг л солино.
    if not partial:
        for f in SETTINGS_FIELDS:
            out.setdefault(f, None)
        if not _load_phones(out["phones"]):
            _bad(conn, "Дор хаяж нэг утасны дугаар шаардлагатай")
    return out


# ============================ Маршрутууд ============================
@bp.route("/api/portal_settings", methods=["GET"])
def get_settings():
    """Одоогийн тохиргоо (мөр байхгүй бол анхдагчаар үүсгэж буцаана)."""
    conn = get_db()
    out = _public(_row(conn))
    conn.close()
    return jsonify(out)


@bp.route("/api/portal_settings", methods=["PUT", "PATCH"])
def update_settings():
    """PUT — бүхэлд нь дарж хадгална; PATCH — ирсэн талбаруудыг л солино."""
    data = json_body()
    conn = get_db()
    current = _row(conn)
    values = _validate(conn, data, partial=request.method == "PATCH")
    fields = list(values)
    conn.execute(
        f"UPDATE portal_settings SET {', '.join(f + '=?' for f in fields)}, "
        "updated_at=? WHERE id=?",
        [values[f] for f in fields] + [now_str(), current["id"]])
    conn.commit()
    row = conn.execute(
        "SELECT * FROM portal_settings WHERE id=?", (current["id"],)).fetchone()
    out = _public(row)
    conn.close()
    # Лого солигдвол хуучныг дискнээс арилгана (гадаад URL-д хүрэхгүй).
    if "logo_url" in values and current["logo_url"] != values["logo_url"]:
        remove_upload(current["logo_url"])
    return jsonify(out)


@bp.route("/api/public/portal_settings", methods=["GET"])
@bp.route("/api/portal/portal_settings", methods=["GET"])
def public_settings():
    """Порталын нээлттэй харагдац — токен шаардахгүй (auth.py-ийн PUBLIC_PREFIXES)."""
    return get_settings()
