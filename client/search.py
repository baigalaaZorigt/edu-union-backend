"""Порталын хайлт (Blueprint) — токенгүй, зөвхөн унших.

    GET /api/portal/search/suggest?q=&limit=8     — гарчгаар, хурдан (dropdown)
        -> {items: [{type, id, title, path, anchor}]}
    GET /api/portal/search?q=&type=&page=1&per_page=10  — гарчиг + их бие
        -> {items: [... + snippet], page, pages, per_page, total}

q нь 2–60 тэмдэгтээс гадуур бол {items: []} (алдаа биш). Индекс, тааруулалт, snippet нь
core/search_core.py-д. Нийтийн endpoint тул:
  * IP тутамд RATE_LIMIT хүсэлт / RATE_WINDOW секунд -> 429. IP-г nginx-ийн X-Real-IP-ээс
    (nginx өөрөө дарж бичдэг; X-Forwarded-For-ийн эхнийхийг клиент хуурамчаар тавьж чадна).
  * Ижил хүсэлтийн хариуг RESULT_TTL секунд кэшилнэ + Cache-Control: max-age=60.
Кэш ба хязгаар нь gunicorn ажилтан (процесс) тус бүрд тусдаа — 3 ажилтантай бол бодит
хязгаар ~3 дахин өндөр. Энэ ачаалалд хангалттай; нарийн хэрэгтэй бол nginx limit_req.
"""
import math
import time
from collections import deque

from flask import Blueprint, abort, jsonify, request

from core import search_core

bp = Blueprint("portal_search", __name__)

RATE_LIMIT, RATE_WINDOW = 30, 60
RESULT_TTL = 60
MAX_CACHE = 500
SUGGEST_DEFAULT, SUGGEST_MAX = 8, 20
PER_PAGE_DEFAULT, PER_PAGE_MAX = 10, 50

_hits = {}          # ip -> deque[timestamp]
_results = {}       # cache key -> (timestamp, payload)


def reset_state():
    """Тестэд: хязгаар, үр дүн, индексийн кэшийг цэвэрлэнэ."""
    _hits.clear()
    _results.clear()
    search_core.clear_cache()


def _rate_limit():
    ip = request.headers.get("X-Real-IP") or request.remote_addr or "?"
    now = time.monotonic()
    q = _hits.setdefault(ip, deque())
    while q and now - q[0] >= RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        abort(429, description="Хэт олон хайлт — түр хүлээгээд дахин оролдоно уу")
    q.append(now)
    if len(_hits) > 10000:                    # санах ой хамгаалах
        _hits.clear()


def _int_arg(name, default, lo, hi):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        return max(lo, min(hi, int(raw)))
    except ValueError:
        abort(400, description=f"{name} нь тоо байх ёстой")


def _cached(key, build):
    now = time.monotonic()
    hit = _results.get(key)
    if hit and now - hit[0] < RESULT_TTL:
        payload = hit[1]
    else:
        payload = build()
        if len(_results) >= MAX_CACHE:
            _results.clear()
        _results[key] = (now, payload)
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = f"public, max-age={RESULT_TTL}"
    return resp


@bp.route("/api/portal/search/suggest", methods=["GET"])
def suggest():
    _rate_limit()
    limit = _int_arg("limit", SUGGEST_DEFAULT, 1, SUGGEST_MAX)
    q = search_core.clean_q(request.args.get("q"))
    if q is None:
        return jsonify(items=[])
    return _cached(("suggest", q.lower(), limit),
                   lambda: {"items": search_core.suggest(q, limit)})


@bp.route("/api/portal/search", methods=["GET"])
def search():
    _rate_limit()
    page = _int_arg("page", 1, 1, 10 ** 6)
    per_page = _int_arg("per_page", PER_PAGE_DEFAULT, 1, PER_PAGE_MAX)
    type_ = request.args.get("type") or None
    if type_ and type_ not in search_core.TYPES:
        abort(400, description="type буруу. Сонголт: " + ", ".join(search_core.TYPES))
    q = search_core.clean_q(request.args.get("q"))
    if q is None:
        return jsonify(items=[], page=page, pages=0, per_page=per_page, total=0)

    def build():
        found = search_core.search(q, type_)
        start = (page - 1) * per_page
        return {"items": found[start:start + per_page], "page": page,
                "pages": math.ceil(len(found) / per_page), "per_page": per_page,
                "total": len(found)}
    return _cached(("search", q.lower(), type_, page, per_page), build)
