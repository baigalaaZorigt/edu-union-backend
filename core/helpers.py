"""Маршрутуудын хуваалцсан туслахууд (admin/ ба client/ хоёулаа ашиглана).

JSON их бие / заавал талбарын шалгалт, allowlist (pick), клиентийн IP, хуудаслалтын
параметр ба хариуны хэлбэр, алдааны JSON боловсруулагч. DB-д хандах туслахууд core/orm/-д.
"""
from datetime import datetime, timezone

from flask import jsonify, abort, request


def now_str():
    """Одоогийн UTC цаг — "YYYY-MM-DD HH:MM:SS" (forms/news/feedback/мэдэгдэл бүгд ижил).

    Текстээр харьцуулахад ч дараалал зөв тул `scheduled_at <= ?` зэрэг шалгалт SQL-д шууд ажиллана.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def require(data, fields):
    """JSON их бие болон заавал талбарууд бүрэн эсэхийг шалгана (дутуу бол 400)."""
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    missing = [f for f in fields if not data.get(f)]
    if missing:
        abort(400, description="Дутуу талбар: " + ", ".join(missing))


def json_body():
    """request-ийн JSON их биеийг буцаана (байхгүй/хоосон бол 400).

    Заавал талбаргүй, хэсэгчилсэн шинэчлэлт (PUT) хийдэг маршрутуудад тохиромжтой.
    """
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    return data


def client_ip():
    """Клиентийн IP: nginx-ийн X-Real-IP (nginx өөрөө дарж бичдэг), эс бөгөөс remote_addr.

    X-Forwarded-For-ийн эхний утгыг клиент хуурамчаар тавьж чадах тул хязгаарлалтад бүү ашигла.
    """
    return request.headers.get("X-Real-IP") or request.remote_addr or "?"


def pick(data, fields, skip_none=False):
    """`data`-аас зөвхөн `fields` allowlist-д байгаа түлхүүрүүдийг (дарааллаар нь) авна.

    skip_none=True бол утга нь None талбаруудыг алгасна (INSERT-д хэрэглэдэг хэв маяг).
    """
    return {f: data[f] for f in fields
            if f in data and not (skip_none and data[f] is None)}


# --- Жагсаалтын хуудаслалт (сонголтоор) ---
# ?page= эсвэл ?per_page= өгвөл {items, total, page, per_page, pages}; аль нь ч өгөөгүй бол
# ХУУЧИН шигээ массив — одоо ажиллаж буй frontend эвдрэхгүй. SQL хуудаслалт нь
# core/orm/query.paginate(); Python-д шүүсэн жагсаалтад slice_page(). forms/feedback/notifications/
# search-ийн хуудаслалттай ижил хэлбэр ба дүрэм (per_page ≤ 100, тоо биш бол 400).
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


def page_params():
    """(page, per_page) эсвэл None (хуудаслалт хүсээгүй)."""
    args = request.args
    if args.get("page") in (None, "") and args.get("per_page") in (None, ""):
        return None
    try:
        page = max(1, int(args.get("page") or 1))
        per_page = min(MAX_PER_PAGE, max(1, int(args.get("per_page") or DEFAULT_PER_PAGE)))
    except ValueError:
        abort(400, description="page / per_page нь тоо байх ёстой")
    return page, per_page


def slice_page(items):
    """Python-д аль хэдийн шүүсэн жагсаалтыг хуудаслана -> (хэсэг, meta | None)."""
    pp = page_params()
    if pp is None:
        return items, None
    page, per_page = pp
    total = len(items)
    return items[(page - 1) * per_page:page * per_page], {
        "total": total, "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page}


def list_json(items, meta):
    """meta байхгүй бол массив, байвал {items, total, page, per_page, pages}."""
    return jsonify(items) if meta is None else jsonify(items=items, **meta)


def register_error_handlers(target):
    """app эсвэл Blueprint дээр алдааг {"error": ...} JSON болгон буцаах нэгдсэн
    боловсруулагчийг бүртгэнэ.

    400 буруу хүсэлт / 401 нэвтрээгүй / 403 эрх хүрэлцэхгүй / 404 олдсонгүй /
    405 буруу метод / 409 давхцал / 413 хэт том хүсэлт (файл оруулах) /
    422 агуулга нь зөв боловч бизнес дүрэмд зөрчсөн (ж: одоогийн нууц үг буруу) /
    429 хэт олон хүсэлт (порталын хайлт).
    """
    @target.errorhandler(400)
    @target.errorhandler(401)
    @target.errorhandler(403)
    @target.errorhandler(404)
    @target.errorhandler(409)
    @target.errorhandler(422)
    @target.errorhandler(429)
    def _handle(err):
        # extra — ж: core.orm.restrict.Referenced-ийн {"references": [...]}
        return jsonify(error=err.description, **getattr(err, "extra", {})), err.code

    @target.errorhandler(405)
    def _bad_method(err):
        # Анхдагчаараа HTML буцдаг тул JSON болгож, зөвшөөрөгдсөн методыг хэлж өгнө.
        allowed = ", ".join(sorted(err.valid_methods or ()))
        return jsonify(error=f"{request.method} метод энэ хаяг дээр ажиллахгүй"
                             + (f" — зөвшөөрөгдөх: {allowed}" if allowed else "")), 405

    @target.errorhandler(413)
    def _too_large(err):
        # Werkzeug-ийн анхдагч тайлбар англи тул монголоор орлуулна.
        return jsonify(error="Хүсэлт хэт том байна — PDF файл тус бүр 10 MB-аас "
                             "хэтрэхгүй, нэг удаад илгээх нийт хэмжээ 50 MB"), 413

    return _handle
