"""member_file (Гишүүний хавсралт — батламж г.м., зөвхөн PDF)."""

import os
import uuid
from datetime import datetime, timezone

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import insert_row, json_body, rows

from admin.union import bp
from admin.union.common import (MEMBER_STORE, _arg_filters, _delete_by_id, _get_one, _list_rows,
                                _purge_orphan_files, _require_row, _update_by_id, _where)


MAX_FILE_SIZE = 10 * 1024 * 1024          # 10 MB (файл тус бүрд)
PDF_MAGIC = b"%PDF-"                       # PDF файлын эхний байтууд
NOT_FOUND = "Файл олдсонгүй"


def _validate_pdf(f):
    """Оруулсан нэг файлыг шалгана: .pdf нэр, PDF агуулга, ≤10 MB. Буруу бол 400.

    DB холболт нээхээс ӨМНӨ дуудна — бүх файлыг эхлээд шалгаж байж хадгална
    (нэг нь буруу бол юу ч хадгалагдахгүй).
    """
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
    if size > MAX_FILE_SIZE:
        abort(400, description=(
            f"'{name}': файл 10 MB-аас хэтэрсэн байна "
            f"({size / 1024 / 1024:.1f} MB)"))
    if f.stream.read(len(PDF_MAGIC)) != PDF_MAGIC:
        f.stream.seek(0)
        abort(400, description=f"'{name}': PDF файл биш байна")
    f.stream.seek(0)
    return name, size


def _save_pdf(f, member_id):
    """Файлыг `<member_id>/<uuid>.pdf` нэрээр (S3 эсвэл диск) хадгалаад stored_name-г буцаана."""
    stored = os.path.join(str(member_id), f"{uuid.uuid4().hex}.pdf")
    MEMBER_STORE.save(stored.replace(os.sep, "/"), f, "application/pdf")
    return stored


@bp.route("/api/member_file", methods=["GET"])
def list_member_file():
    cond, params = _arg_filters(("member_id",))
    return _list_rows("SELECT * FROM member_file" + _where(cond) + " ORDER BY id", params)


@bp.route("/api/member_file/<int:fid>", methods=["GET"])
def get_member_file(fid):
    return _get_one("SELECT * FROM member_file WHERE id=?", (fid,), NOT_FOUND)


@bp.route("/api/member_file/<int:fid>/download", methods=["GET"])
def download_member_file(fid):
    """Файлын агуулгыг PDF-ээр буцаана (анхны нэрээр нь татагдана)."""
    conn = get_db()
    row = conn.execute("SELECT * FROM member_file WHERE id=?", (fid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description=NOT_FOUND)
    resp = MEMBER_STORE.send(row["stored_name"].replace(os.sep, "/"), "application/pdf",
                             download_name=row["file_name"])
    if resp is None:
        abort(404, description="Файлын агуулга дискнээс олдсонгүй")
    return resp


@bp.route("/api/member_file", methods=["POST"])
def upload_member_file():
    """Гишүүнд PDF хавсралт(ууд) оруулна — multipart/form-data.

    Талбарууд: member_id (заавал), file (олон удаа давтаж болно), note (сонголтоор).
    """
    member_id = (request.form.get("member_id") or "").strip()
    if not member_id.isdigit():
        abort(400, description="member_id (тоо) шаардлагатай — multipart/form-data-аар илгээнэ")
    files = [f for f in request.files.getlist("file") + request.files.getlist("files") if f]
    if not files:
        abort(400, description="Файл алга — 'file' талбараар (олон байж болно) илгээнэ")

    checked = [_validate_pdf(f) for f in files]   # бүгд зөв эсэхийг эхлээд шалгана

    conn = get_db()
    _require_row(conn, "member", member_id, "member_id (эцэг гишүүн) олдсонгүй")
    note = request.form.get("note")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_ids = [
        insert_row(conn, "member_file", {
            "member_id": member_id, "file_name": name, "stored_name": _save_pdf(f, member_id),
            "size": size, "note": note, "uploaded_at": now})
        for f, (name, size) in zip(files, checked)]
    conn.commit()
    ph = ", ".join("?" * len(new_ids))
    data = rows(conn.execute(
        f"SELECT * FROM member_file WHERE id IN ({ph}) ORDER BY id", new_ids).fetchall())
    conn.close()
    return jsonify(data), 201


@bp.route("/api/member_file/<int:fid>", methods=["PUT", "PATCH"])
def update_member_file(fid):
    """Зөвхөн тайлбарыг (note) засна — файлын агуулгыг солихгүй (дахин оруулна)."""
    data = json_body()
    if "note" not in data:
        abort(400, description="Шинэчлэх талбар алга (note)")
    return _update_by_id(get_db(), "member_file", fid, {"note": data["note"]}, NOT_FOUND)


@bp.route("/api/member_file/<int:fid>", methods=["DELETE"])
def delete_member_file(fid):
    # мөр устсаны дараа дискнээс нь ч арилгана
    return _delete_by_id(get_db(), "member_file", fid, NOT_FOUND, _purge_orphan_files)
