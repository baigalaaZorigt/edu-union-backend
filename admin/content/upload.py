"""upload (Файл байршуулах) — /api/upload ба /uploads/content/<нэр> (токенгүй)."""

import os

from flask import jsonify, request, abort

from admin.content import bp
from core.content_storage import STORE, save_upload


# ===================== upload (Файл байршуулах) =====================
@bp.route("/api/upload", methods=["POST"])
def upload():
    """multipart/form-data, `file` талбар -> {url, name, mime_type, size}.

    Буцаж ирсэн url-г page.cover_image эсвэл блокийн url талбарт хадгална.
    """
    f = (request.files.get("file") or
         (request.files.getlist("file") or [None])[0])
    if not f:
        abort(400, description="Файл алга — 'file' талбараар илгээнэ")
    return jsonify(save_upload(f)), 201


@bp.route("/uploads/content/<path:stored_name>", methods=["GET"])
def serve_upload(stored_name):
    """Байршуулсан файлыг үйлчилнэ — токен шаардахгүй (порталд <img>-ээр ачаална).

    auth.py-ийн PUBLIC_PREFIXES энэ замыг нээлттэй болгодог.
    """
    resp = STORE.send(os.path.basename(stored_name))
    if resp is None:
        abort(404, description="Файл олдсонгүй")
    return resp
