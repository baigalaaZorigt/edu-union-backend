"""Санал асуулгын PDF (form_document) — шалгалт, жагсаалт, дискнээс устгал."""
import os

from flask import abort
from sqlalchemy import select

from core.orm import session
from core.orm.models import FormDocument
from core.storage import Area

# --- Санал асуулгын PDF (form_document) ---
# Порталын PDF viewer толгой дамжуулж чаддаггүй тул байршуулсан файлыг
# /uploads/form/ дороос токенгүй үйлчилнэ (auth.py-ийн PUBLIC_PREFIXES).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo-ийн үндэс
UPLOAD_DIR = os.environ.get("FORM_UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "form"))
UPLOAD_URL_PREFIX = "/uploads/form/"
STORE = Area("form", UPLOAD_DIR)       # S3 (S3_BUCKET) эсвэл FORM_UPLOAD_DIR
MAX_PDF_SIZE = 20 * 1024 * 1024            # PDF ≤ 20 MB
PDF_MAGIC = b"%PDF-"


# ----------------------------- form_document (PDF) -----------------------------
def public_document(row):
    return {"id": row["id"], "form_id": row["form_id"], "file_name": row["file_name"],
            "file_path": row["file_path"], "url": row["file_path"],
            "mime_type": row["mime_type"], "file_size": row["file_size"],
            "created_at": row["created_at"]}


def validate_pdf(f):
    """Нэг PDF-г шалгана: .pdf нэр, %PDF- толгой, ≤20 MB (буруу бол 400) -> (нэр, хэмжээ)."""
    name = (f.filename or "").strip()
    if not name:
        abort(400, description="Файлын нэр хоосон байна")
    if not name.lower().endswith(".pdf"):
        abort(400, description=f"'{name}': зөвхөн PDF файл оруулна")
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        abort(400, description=f"'{name}': файл хоосон байна")
    if size > MAX_PDF_SIZE:
        abort(400, description=(f"'{name}': файл 20 MB-аас хэтэрсэн байна "
                                f"({size / 1024 / 1024:.1f} MB)"))
    if f.stream.read(len(PDF_MAGIC)) != PDF_MAGIC:
        f.stream.seek(0)
        abort(400, description=f"'{name}': PDF файл биш байна")
    f.stream.seek(0)
    return name, size


def document_list(form_id):
    return [public_document(d.to_dict()) for d in session().scalars(
        select(FormDocument).where(FormDocument.form_id == form_id).order_by(FormDocument.id))]


def remove_upload(file_path):
    """Байршуулсан PDF-г сангаас (S3/диск) арилгана (зөвхөн өөрсдийн угтвартай замыг)."""
    if not file_path or not file_path.startswith(UPLOAD_URL_PREFIX):
        return
    STORE.delete(os.path.basename(file_path))
