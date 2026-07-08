"""Маршрутуудын хуваалцсан туслахууд.

app.py, union.py, users.py гурвуулаа эдгээрийг ашиглана — өмнө нь файл бүрт
тус тусад нь давхардуулж бичсэн байсныг нэг дор нэгтгэв.
"""
from flask import jsonify, abort, request


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


def register_error_handlers(target):
    """app эсвэл Blueprint дээр алдааг {"error": ...} JSON болгон буцаах нэгдсэн
    боловсруулагчийг бүртгэнэ.

    400 буруу хүсэлт / 401 нэвтрээгүй / 403 эрх хүрэлцэхгүй / 404 олдсонгүй / 409 давхцал.
    """
    @target.errorhandler(400)
    @target.errorhandler(401)
    @target.errorhandler(403)
    @target.errorhandler(404)
    @target.errorhandler(409)
    def _handle(err):
        return jsonify(error=err.description), err.code

    return _handle
