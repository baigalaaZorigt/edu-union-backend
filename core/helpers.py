"""Маршрутуудын хуваалцсан туслахууд (admin/ ба client/ хоёулаа ашиглана).

Өмнө нь файл бүрт тус тусад нь давхардуулж бичсэн байсныг нэг дор нэгтгэв:
JSON их бие / заавал талбарын шалгалт, холболтыг хаагаад abort хийх, талбарын
allowlist-ээс INSERT / UPDATE бүтээх, алдааны JSON боловсруулагч.
"""
from datetime import datetime, timezone

from flask import jsonify, abort, request


def now_str():
    """Одоогийн UTC цаг — "YYYY-MM-DD HH:MM:SS" (forms/news/feedback/мэдэгдэл бүгд ижил).

    Текстээр харьцуулахад ч дараалал зөв тул `scheduled_at <= ?` зэрэг шалгалт SQL-д шууд ажиллана.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def rows(cursor_rows):
    """sqlite3.Row-ийн жагсаалтыг энгийн dict-ийн жагсаалт болгоно."""
    return [dict(r) for r in cursor_rows]


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


def fail(conn, code, message):
    """Холболтыг хаагаад `abort(code)` хийнэ — "close-before-abort" дүрмийг нэг мөрөнд.

    Маршрут бүр холболтоо өөрөө хаах ёстой; эрт abort хийвэл холболт алдагдана.
    """
    conn.close()
    abort(code, description=message)


def pick(data, fields, skip_none=False):
    """`data`-аас зөвхөн `fields` allowlist-д байгаа түлхүүрүүдийг (дарааллаар нь) авна.

    skip_none=True бол утга нь None талбаруудыг алгасна (INSERT-д хэрэглэдэг хэв маяг).
    """
    return {f: data[f] for f in fields
            if f in data and not (skip_none and data[f] is None)}


def insert_row(conn, table, values):
    """`values` dict-ээс INSERT бүтээж ажиллуулна; шинэ мөрийн id-г буцаана.

    Хүснэгт/баганын нэр нь үргэлж кодын allowlist-ээс ирнэ (хэрэглэгчийн оролтоос биш).
    """
    cols = list(values)
    cur = conn.execute(
        f"INSERT INTO {table}({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [values[c] for c in cols])
    return cur.lastrowid


def update_row(conn, table, key_value, values, key="id"):
    """`values` dict-ээр `table`-ийн нэг мөрийг шинэчилнэ; нөлөөлсөн мөрийн тоог буцаана."""
    cols = list(values)
    cur = conn.execute(
        f"UPDATE {table} SET {', '.join(c + '=?' for c in cols)} WHERE {key}=?",
        [values[c] for c in cols] + [key_value])
    return cur.rowcount


def register_error_handlers(target):
    """app эсвэл Blueprint дээр алдааг {"error": ...} JSON болгон буцаах нэгдсэн
    боловсруулагчийг бүртгэнэ.

    400 буруу хүсэлт / 401 нэвтрээгүй / 403 эрх хүрэлцэхгүй / 404 олдсонгүй /
    405 буруу метод / 409 давхцал / 413 хэт том хүсэлт (файл оруулах) /
    422 агуулга нь зөв боловч бизнес дүрэмд зөрчсөн (ж: одоогийн нууц үг буруу).
    """
    @target.errorhandler(400)
    @target.errorhandler(401)
    @target.errorhandler(403)
    @target.errorhandler(404)
    @target.errorhandler(409)
    @target.errorhandler(422)
    def _handle(err):
        return jsonify(error=err.description), err.code

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
