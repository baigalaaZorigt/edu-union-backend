"""Байршуулсан контент файлын сан — хадгалах газар, хязгаар, шалгалт, хадгалах, устгах.

admin (POST /api/upload) ба client (POST /api/portal/upload) хоёулаа ашиглана.
"""
import os
import uuid

from flask import abort

from core.storage import Area


# --- Байршуулсан файлын сан ---
# Зураг/файлыг эхлээд /api/upload руу илгээж, буцаж ирсэн URL-г блокод хадгална.
# Production-д S3 (core/storage.py, S3_BUCKET); локал/тестэд CONTENT_UPLOAD_DIR хавтас.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo-ийн үндэс
UPLOAD_DIR = os.environ.get(
    "CONTENT_UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "content"))
UPLOAD_URL_PREFIX = "/uploads/content/"     # энэ URL-ээр буцаан үйлчилнэ (токенгүй)
STORE = Area("content", UPLOAD_DIR)

MAX_IMAGE_SIZE = 5 * 1024 * 1024            # зураг ≤ 5 MB
MAX_DOC_SIZE = 20 * 1024 * 1024             # файл ≤ 20 MB

# Зөвшөөрөгдөх өргөтгөл -> MIME төрөл
IMAGE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp",
}
DOC_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def remove_upload(url):
    """Бидний өөрсдийн байршуулсан файл бол сангаас (S3/диск) арилгана (гадаад URL-д хүрэхгүй).

    admin/news.py мөн үүнийг ашиглана — мэдээний блок/ковер зураг ч /api/upload-аар
    ирдэг тул устгах логик нэг дор байх ёстой.
    """
    if not url or not url.startswith(UPLOAD_URL_PREFIX):
        return
    STORE.delete(os.path.basename(url))


def validate_upload(f):
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


def save_upload(f):
    """Шалгаад хадгална -> {url, name, mime_type, size} (POST /api/upload-ийн хариу)."""
    name, ext, mime, size = validate_upload(f)
    stored = f"{uuid.uuid4().hex}.{ext}"
    STORE.save(stored, f, mime)
    return {"url": UPLOAD_URL_PREFIX + stored, "name": name, "mime_type": mime, "size": size}
