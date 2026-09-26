"""Байршуулсан файлын сан — хадгалах газар, хэмжээ/төрлийн хязгаар, файл устгах."""

import os

from core.storage import Area


# --- Байршуулсан файлын сан ---
# Зураг/файлыг эхлээд /api/upload руу илгээж, буцаж ирсэн URL-г блокод хадгална.
# Production-д S3 (core/storage.py, S3_BUCKET); локал/тестэд CONTENT_UPLOAD_DIR хавтас.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
