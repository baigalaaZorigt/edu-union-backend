"""Хууль тогтоомж — ПОРТАЛ тал (Blueprint, токенгүй).

    GET /api/portal/legal_documents        — is_visible мөрүүд (sort_order, огноо ↓)
                                             {items: [{id, title, category, published_date,
                                                       source_name, display_mode,
                                                       external_url, pdf_url}]}
    GET /api/portal/legal_documents/<id>   — нэг мөр + blocks (detail горимд); нуусан /
                                             байхгүй бол 404 {error}

`legal` төрлийн цэс энэ жагсаалтыг дууддаг (`news` цэс /api/portal/news-ийг дууддаг шиг).
"""
from flask import Blueprint, abort, jsonify
from sqlalchemy import select

from core.legal_core import public_block, public_document
from core.orm import session
from core.orm.models import LegalDocument, LegalDocumentBlock

bp = Blueprint("portal_legal", __name__)


@bp.route("/api/portal/legal_documents", methods=["GET"])
def list_documents():
    rows = session().scalars(
        select(LegalDocument).where(LegalDocument.is_visible == 1)
        .order_by(LegalDocument.sort_order, LegalDocument.published_date.desc().nulls_last(),
                  LegalDocument.id))
    return jsonify(items=[public_document(d) for d in rows])


@bp.route("/api/portal/legal_documents/<int:did>", methods=["GET"])
def get_document(did):
    doc = session().get(LegalDocument, did)
    if doc is None or not doc.is_visible:
        abort(404, description="Баримт олдсонгүй")
    blocks = session().scalars(
        select(LegalDocumentBlock).where(LegalDocumentBlock.legal_document_id == did)
        .order_by(LegalDocumentBlock.sort_order, LegalDocumentBlock.id))
    return jsonify({**public_document(doc), "blocks": [public_block(b) for b in blocks]})
