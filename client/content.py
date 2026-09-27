"""Порталын цэс ба контент — ТОКЕНГҮЙ (Blueprint). Хариу нь admin-ийнхтэй ЯГ ижил хэлбэр.

    GET  /api/portal/menu                  = GET /api/menu (?tree=1, ?parent_id=, ?type=,
                                             ?page=/?per_page=) — ЗӨВХӨН харагдах цэс
                                             (өөрөө болон эцгүүд нь is_visible=1)
    GET  /api/portal/page/<menu_id>        = GET /api/page/<menu_id> — зөвхөн published
                                             хуудас + харагдах цэс; эс бөгөөс 404
    GET  /api/portal/page_block?page_id=   = GET /api/page_block — зөвхөн дээрх хуудсуудын
    POST /api/portal/upload                = POST /api/upload — ижил төрөл/хэмжээний хязгаар
                                             + IP тутамд UPLOAD_LIMIT / UPLOAD_WINDOW сек (429)

Хэлбэржүүлэлт core/content_core.py, файл core/content_storage.py — admin-тай хуваалцана.
Нууцалсан цэс, ноорог хуудас порталд хэзээ ч гарахгүй.
"""
import time
from collections import deque

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import select

from core.content_core import (BLOCK_ORDER, MENU_SELECT, TRUE_ARGS, eq_arg, menu_dict,
                               menu_filters, page_payload, public_block, public_page_ids, tree)
from core.content_storage import save_upload
from core.helpers import client_ip, list_json
from core.orm import session
from core.orm.models import Page, PageBlock
from core.orm.query import paginate

bp = Blueprint("portal_content", __name__)

UPLOAD_LIMIT, UPLOAD_WINDOW = 10, 600          # 10 минутад 10 файл / IP (ажилтан тутамд)
_uploads = {}                                  # ip -> deque[timestamp]


@bp.route("/api/portal/menu", methods=["GET"])
def list_menu():
    stmt = menu_filters(MENU_SELECT, request.args, public=True)
    if request.args.get("tree") in TRUE_ARGS:          # мод бүтэн байх ёстой — хуудаслахгүй
        rows = session().execute(stmt).mappings().all()
        return jsonify(tree([menu_dict(r) for r in rows]))
    rows, meta = paginate(stmt, mappings=True)
    return list_json([menu_dict(r) for r in rows], meta)


@bp.route("/api/portal/page/<int:menu_id>", methods=["GET"])
def get_page(menu_id):
    page = session().scalar(select(Page).where(Page.menu_id == menu_id))
    if page is None or page.id not in public_page_ids():
        abort(404, description="Энэ цэсэнд контент хуудас алга")
    return jsonify(page_payload(page))


@bp.route("/api/portal/page_block", methods=["GET"])
def list_page_block():
    stmt = select(PageBlock).where(PageBlock.page_id.in_(public_page_ids()))
    if request.args.get("page_id"):
        stmt = stmt.where(eq_arg(PageBlock.page_id, request.args["page_id"]))
    if request.args.get("type"):
        stmt = stmt.where(PageBlock.type == request.args["type"])
    blocks, meta = paginate(stmt.order_by(*BLOCK_ORDER))
    return list_json([public_block(b) for b in blocks], meta)


def _upload_rate_limit():
    ip, now = client_ip(), time.monotonic()
    q = _uploads.setdefault(ip, deque())
    while q and now - q[0] >= UPLOAD_WINDOW:
        q.popleft()
    if len(q) >= UPLOAD_LIMIT:
        abort(429, description="Хэт олон файл илгээлээ — түр хүлээгээд дахин оролдоно уу")
    q.append(now)
    if len(_uploads) > 10000:                  # санах ой хамгаалах
        _uploads.clear()


@bp.route("/api/portal/upload", methods=["POST"])
def upload():
    """multipart/form-data, `file` -> {url, name, mime_type, size} (201) — POST /api/upload шиг."""
    f = request.files.get("file") or (request.files.getlist("file") or [None])[0]
    if not f:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    _upload_rate_limit()
    return jsonify(save_upload(f)), 201
