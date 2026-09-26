"""form_document (Санал асуулгын PDF) — байршуулах, жагсаах, устгах, токенгүй үйлчлэх."""

import os
import uuid

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import insert_row
from core.forms_core import (
    STORE, UPLOAD_URL_PREFIX, bad, now_str, public_document, document_list,
    remove_upload, require_form, validate_pdf,
)

from admin.forms import bp


# ====================== form_document (Санал асуулгын PDF) ======================
@bp.route("/api/admin/forms/<int:fid>/documents", methods=["GET"])
def list_documents(fid):
    conn = get_db()
    require_form(conn, fid)
    data = document_list(conn, fid)
    conn.close()
    return jsonify(data)


@bp.route("/api/admin/forms/<int:fid>/document", methods=["POST"])
def upload_document(fid):
    """Маягтад PDF хавсаргах — multipart/form-data, `file` талбар (олон байж болно).

    Бүх файлыг ЭХЛЭЭД шалгана — нэг нь буруу бол юу ч хадгалагдахгүй.
    """
    files = [f for f in request.files.getlist("file") + request.files.getlist("files") if f]
    if not files:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    checked = [validate_pdf(f) for f in files]
    conn = get_db()
    require_form(conn, fid)
    now = now_str()
    new_ids = []
    for f, (name, size) in zip(files, checked):
        stored = f"{uuid.uuid4().hex}.pdf"
        STORE.save(stored, f, "application/pdf")
        new_ids.append(insert_row(conn, "form_document", {
            "form_id": fid, "file_name": name, "file_path": UPLOAD_URL_PREFIX + stored,
            "mime_type": "application/pdf", "file_size": size, "created_at": now}))
    conn.commit()
    ph = ", ".join("?" * len(new_ids))
    data = [public_document(r) for r in conn.execute(
        f"SELECT * FROM form_document WHERE id IN ({ph}) ORDER BY id", new_ids).fetchall()]
    conn.close()
    return jsonify(data), 201


@bp.route("/api/admin/documents/<int:did>", methods=["DELETE"])
def delete_document(did):
    conn = get_db()
    row = conn.execute("SELECT * FROM form_document WHERE id=?", (did,)).fetchone()
    if not row:
        bad(conn, "Файл олдсонгүй", 404)
    conn.execute("DELETE FROM form_document WHERE id=?", (did,))
    conn.commit()
    conn.close()
    remove_upload(row["file_path"])
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
