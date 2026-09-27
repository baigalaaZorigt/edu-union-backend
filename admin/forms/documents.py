"""form_document (Санал асуулгын PDF) — байршуулах, жагсаах, устгах, токенгүй үйлчлэх."""

import os
import uuid

from flask import jsonify, request, abort
from sqlalchemy import delete

from core.orm import session
from core.orm.models import FormDocument
from core.forms_core import (
    STORE, UPLOAD_URL_PREFIX, bad, now_str, public_document, document_list,
    remove_upload, require_form, validate_pdf,
)

from admin.forms import bp


# ====================== form_document (Санал асуулгын PDF) ======================
@bp.route("/api/admin/forms/<int:fid>/documents", methods=["GET"])
def list_documents(fid):
    require_form(fid)
    return jsonify(document_list(fid))


@bp.route("/api/admin/forms/<int:fid>/document", methods=["POST"])
def upload_document(fid):
    """Маягтад PDF хавсаргах — multipart/form-data, `file` талбар (олон байж болно).

    Бүх файлыг ЭХЛЭЭД шалгана — нэг нь буруу бол юу ч хадгалагдахгүй.
    """
    files = [f for f in request.files.getlist("file") + request.files.getlist("files") if f]
    if not files:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    checked = [validate_pdf(f) for f in files]
    require_form(fid)
    s = session()
    now = now_str()
    docs = []
    for f, (name, size) in zip(files, checked):
        stored = f"{uuid.uuid4().hex}.pdf"
        STORE.save(stored, f, "application/pdf")
        doc = FormDocument(form_id=fid, file_name=name, file_path=UPLOAD_URL_PREFIX + stored,
                           mime_type="application/pdf", file_size=size, created_at=now)
        s.add(doc)
        docs.append(doc)
    s.commit()
    return jsonify([public_document(d.to_dict()) for d in sorted(docs, key=lambda d: d.id)]), 201


@bp.route("/api/admin/documents/<int:did>", methods=["DELETE"])
def delete_document(did):
    s = session()
    doc = s.get(FormDocument, did)
    if doc is None:
        bad("Файл олдсонгүй", 404)
    path = doc.file_path
    s.execute(delete(FormDocument).where(FormDocument.id == did))
    s.commit()
    remove_upload(path)
    return jsonify(deleted=did)


@bp.route("/uploads/form/<path:stored_name>", methods=["GET"])
def serve_form_document(stored_name):
    """Хавсаргасан PDF-г үйлчилнэ — токен шаардахгүй (порталын PDF viewer).

    auth.py-ийн PUBLIC_PREFIXES ("/uploads/") энэ замыг нээлттэй болгодог.
    """
    resp = STORE.send(os.path.basename(stored_name), mimetype="application/pdf")
    if resp is None:
        abort(404, description="Файл олдсонгүй")
    return resp
