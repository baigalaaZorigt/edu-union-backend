"""Хууль тогтоомж — АДМИН тал (Blueprint). Токен + legal_document.* эрх.

    GET    /api/legal_document                       — бүх мөр (нуусан ч), sort_order, огноо ↓
    POST   /api/legal_document                       — {title, category, published_date,
                                                        source_name, display_mode,
                                                        external_url, pdf_url, sort_order,
                                                        is_visible}
    GET|PUT|PATCH|DELETE /api/legal_document/<id>
    GET    /api/legal_document/<id>/blocks           — блокууд (sort_order)
    POST   /api/legal_document/<id>/blocks           — {type, sort_order?, ...төрлийн талбар}
    POST   /api/legal_document/<id>/blocks/reorder   — {blocks: [{id, sort_order}, ...]}
    GET|PUT|PATCH|DELETE /api/legal_document_block/<id>

Блокийн замууд ч legal_document.* эрхээр (auth.py: SUB_RESOURCE/PATH_RESOURCE).
PDF-ийг /api/upload-оор оруулна; солигдох/устгах үед файл сангаас (S3/диск) арилна.
"""
from flask import Blueprint, abort, jsonify
from sqlalchemy import func, select

from core.helpers import json_body, list_json
from core.legal_core import (admin_document, public_block, validate_block,
                             validate_document)
from core.orm import session
from core.orm.models import LegalDocument, LegalDocumentBlock
from core.orm.query import get_or_404, paginate
from admin.content import remove_upload

bp = Blueprint("legal", __name__)

NOT_FOUND = "Баримт олдсонгүй"
BLOCK_NOT_FOUND = "Блок олдсонгүй"
ORDER = (LegalDocument.sort_order, LegalDocument.published_date.desc().nulls_last(),
         LegalDocument.id)


def _blocks(doc_id):
    return session().scalars(select(LegalDocumentBlock)
                             .where(LegalDocumentBlock.legal_document_id == doc_id)
                             .order_by(LegalDocumentBlock.sort_order, LegalDocumentBlock.id)).all()


# ============================ legal_document ============================
@bp.route("/api/legal_document", methods=["GET"])
def list_documents():
    items, meta = paginate(select(LegalDocument).order_by(*ORDER))
    return list_json([admin_document(d) for d in items], meta)


@bp.route("/api/legal_document/<int:did>", methods=["GET"])
def get_document(did):
    doc = get_or_404(LegalDocument, did, NOT_FOUND)
    return jsonify({**admin_document(doc), "blocks": [public_block(b) for b in _blocks(did)]})


@bp.route("/api/legal_document", methods=["POST"])
def create_document():
    doc = LegalDocument(**validate_document(json_body()))
    s = session()
    s.add(doc)
    s.commit()
    return jsonify(admin_document(doc)), 201


@bp.route("/api/legal_document/<int:did>", methods=["PUT", "PATCH"])
def update_document(did):
    data = json_body()
    doc = get_or_404(LegalDocument, did, NOT_FOUND)
    values = validate_document(data, doc.to_dict())
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    old_pdf = doc.pdf_url
    for k, v in values.items():
        setattr(doc, k, v)
    session().commit()
    if "pdf_url" in values and values["pdf_url"] != old_pdf:
        remove_upload(old_pdf)
    return jsonify(admin_document(doc))


@bp.route("/api/legal_document/<int:did>", methods=["DELETE"])
def delete_document(did):
    doc = get_or_404(LegalDocument, did, NOT_FOUND)
    files = [doc.pdf_url] + [b.url for b in _blocks(did) if b.type == "file"]
    s = session()
    s.delete(doc)                     # блокууд DB-ийн ON DELETE CASCADE-аар
    s.commit()
    for url in files:
        remove_upload(url)
    return jsonify(deleted=did)


# ========================= legal_document_block =========================
@bp.route("/api/legal_document/<int:did>/blocks", methods=["GET"])
def list_blocks(did):
    get_or_404(LegalDocument, did, NOT_FOUND)
    return jsonify([public_block(b) for b in _blocks(did)])


@bp.route("/api/legal_document/<int:did>/blocks", methods=["POST"])
def create_block(did):
    data = json_body()
    get_or_404(LegalDocument, did, NOT_FOUND)
    btype, values = validate_block(data)
    s = session()
    if "sort_order" not in values:
        values["sort_order"] = (s.scalar(select(func.max(LegalDocumentBlock.sort_order))
                                .where(LegalDocumentBlock.legal_document_id == did)) or 0) + 1
    block = LegalDocumentBlock(legal_document_id=did, type=btype, **values)
    s.add(block)
    s.commit()
    return jsonify(public_block(block)), 201


@bp.route("/api/legal_document/<int:did>/blocks/reorder", methods=["POST", "PUT", "PATCH"])
def reorder_blocks(did):
    """{"blocks": [{"id": 5, "sort_order": 1}, ...]} — /admin/forms/<id>/questions/reorder шиг."""
    data = json_body()
    items = data.get("blocks")
    if not isinstance(items, list) or not items:
        abort(400, description="blocks (жагсаалт) шаардлагатай")
    get_or_404(LegalDocument, did, NOT_FOUND)
    s = session()
    updates = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            abort(400, description="blocks доторх бичлэг бүр id-тай байна")
        block = s.scalar(select(LegalDocumentBlock).where(
            LegalDocumentBlock.id == int(item["id"]), LegalDocumentBlock.legal_document_id == did))
        if block is None:
            abort(404, description=f"Энэ баримтад харьяалагдахгүй блок: {item['id']}")
        updates.append((block, item.get("sort_order") or i))
    for block, order in updates:
        block.sort_order = order
    s.commit()
    return jsonify([public_block(b) for b in _blocks(did)])


@bp.route("/api/legal_document_block/<int:bid>", methods=["GET"])
def get_block(bid):
    return jsonify(public_block(get_or_404(LegalDocumentBlock, bid, BLOCK_NOT_FOUND)))


@bp.route("/api/legal_document_block/<int:bid>", methods=["PUT", "PATCH"])
def update_block(bid):
    data = json_body()
    block = get_or_404(LegalDocumentBlock, bid, BLOCK_NOT_FOUND)
    _, values = validate_block(data, current_type=block.type)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    old_url = block.url
    for k, v in values.items():
        setattr(block, k, v)
    session().commit()
    if block.type == "file" and "url" in values and values["url"] != old_url:
        remove_upload(old_url)
    return jsonify(public_block(block))


@bp.route("/api/legal_document_block/<int:bid>", methods=["DELETE"])
def delete_block(bid):
    block = get_or_404(LegalDocumentBlock, bid, BLOCK_NOT_FOUND)
    url = block.url if block.type == "file" else None
    s = session()
    s.delete(block)
    s.commit()
    remove_upload(url)
    return jsonify(deleted=bid)
