"""upload (Файл байршуулах) — /api/upload ба /uploads/content/<нэр> (токенгүй)."""

import os
import uuid

from flask import jsonify, request, abort, send_from_directory

from admin.content import bp
from admin.content.storage import (DOC_TYPES, IMAGE_TYPES, MAX_DOC_SIZE, MAX_IMAGE_SIZE,
                                   UPLOAD_DIR, UPLOAD_URL_PREFIX)


# ===================== upload (Файл байршуулах) =====================
def _validate_upload(f):
    """Өргөтгөл ба хэмжээг шалгаад (нэр, өргөтгөл, mime, хэмжээ)-г буцаана."""
    name = (f.filename or "").strip()
    if not name or "." not in name:
        abort(400, description="Файлын нэр буруу байна")
    ext = name.rsplit(".", 1)[1].lower()
    if ext in IMAGE_TYPES:
        mime, limit, label = IMAGE_TYPES[ext], MAX_IMAGE_SIZE, "Зураг 5 MB"
    elif ext in DOC_TYPES:
        mime, limit, label = DOC_TYPES[ext], MAX_DOC_SIZE, "Файл 20 MB"
    else:
        abort(400, description=(
            "Зөвшөөрөгдөөгүй төрөл. Зураг: " + ", ".join(IMAGE_TYPES) +
            " / Файл: " + ", ".join(DOC_TYPES)))
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        abort(400, description=f"'{name}': файл хоосон байна")
    if size > limit:
        abort(400, description=(
            f"'{name}': {label}-аас хэтэрсэн байна ({size / 1024 / 1024:.1f} MB)"))
    return name, ext, mime, size


@bp.route("/api/upload", methods=["POST"])
def upload():
    """multipart/form-data, `file` талбар -> {url, name, mime_type, size}.

    Буцаж ирсэн url-г page.cover_image эсвэл блокийн url талбарт хадгална.
    """
    f = (request.files.get("file") or
         (request.files.getlist("file") or [None])[0])
    if not f:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    name, ext, mime, size = _validate_upload(f)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(UPLOAD_DIR, stored))
    return jsonify(url=UPLOAD_URL_PREFIX + stored,
                   name=name, mime_type=mime, size=size), 201


@bp.route("/uploads/content/<path:stored_name>", methods=["GET"])
def serve_upload(stored_name):
    """Байршуулсан файлыг үйлчилнэ — токен шаардахгүй (порталд <img>-ээр ачаална).

    auth.py-ийн PUBLIC_PREFIXES энэ замыг нээлттэй болгодог.
    """
    name = os.path.basename(stored_name)
    if not os.path.isfile(os.path.join(UPLOAD_DIR, name)):
        abort(404, description="Файл олдсонгүй")
    return send_from_directory(UPLOAD_DIR, name)
