"""Байршуулсан файлын сан — хадгалах хавтас, хэмжээ/төрлийн хязгаар, файл устгах."""

import os


# --- Байршуулсан файлын сан ---
# Зураг/файлыг эхлээд /api/upload руу илгээж, буцаж ирсэн URL-г блокод хадгална.
# CONTENT_UPLOAD_DIR орчны хувьсагчаар өөрчилнө (Render дээр тогтвортой disk руу заа).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.environ.get(
    "CONTENT_UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "content"))
UPLOAD_URL_PREFIX = "/uploads/content/"     # энэ URL-ээр буцаан үйлчилнэ (токенгүй)

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
    """Бидний өөрсдийн байршуулсан файл бол дискнээс арилгана (гадаад URL-д хүрэхгүй).

    admin/news.py мөн үүнийг ашиглана — мэдээний блок/ковер зураг ч /api/upload-аар
    ирдэг тул устгах логик нэг дор байх ёстой.
    """
    if not url or not url.startswith(UPLOAD_URL_PREFIX):
        return
    path = os.path.join(UPLOAD_DIR, os.path.basename(url))
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass    # диск дээрх файл арилгаж чадаагүй ч DB-гийн мөр устсан хэвээр
