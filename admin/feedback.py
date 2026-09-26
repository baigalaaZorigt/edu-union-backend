"""Санал хүсэлт, Өргөдөл гомдлын АДМИН тал (Blueprint).

Замын угтвар: /api/admin/... — жагсаалт (хайлт + хуудаслалт) ба устгал.
Порталын тал (маягт илгээх, токенгүй) нь client/feedback.py дотор.

**"Нэгийг авах" маршрут байхгүй** (спек §4): жагсаалтын хариунд message /
description хамт бүрэн ирдэг тул админы 👁 дэлгэрэнгүй модаль нь татсан
датагаа шууд харуулна.

**Төлөв солих маршрут ч байхгүй**: `status` багана `'new'` хэвээр байна —
V1-д UI үүнийг ашиглахгүй тул спек зориуд орхисон (§2).
"""
from flask import Blueprint, jsonify, request

from core.db import get_db
from core.feedback_core import KINDS, list_page
from core.helpers import fail
from admin.content import remove_upload

bp = Blueprint("admin_feedback", __name__)


def _list(kind):
    conn = get_db()
    out = list_page(conn, kind, request.args)
    conn.close()
    return jsonify(out)


def _delete(kind, rid):
    """Мөрийг устгана; өргөдлийн хавсралт байвал дискнээс нь ч арилгана."""
    spec = KINDS[kind]
    conn = get_db()
    row = conn.execute(f"SELECT * FROM {spec['table']} WHERE id=?", (rid,)).fetchone()
    if not row:
        fail(conn, 404, spec["label"] + " олдсонгүй")
    conn.execute(f"DELETE FROM {spec['table']} WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if "file_url" in spec["optional"]:
        remove_upload(row["file_url"])      # зөвхөн /uploads/content/-ийн доорхыг
    return jsonify(deleted=rid)


# ===================== suggestions (Санал хүсэлт) =====================
@bp.route("/api/admin/suggestions", methods=["GET"])
def list_suggestions():
    """Санал хүсэлтийн жагсаалт. Шүүлт: ?search= &page= &per_page="""
    return _list("suggestions")


@bp.route("/api/admin/suggestions/<int:rid>", methods=["DELETE"])
def delete_suggestion(rid):
    return _delete("suggestions", rid)


# ================== complaints (Өргөдөл, гомдол) ==================
@bp.route("/api/admin/complaints", methods=["GET"])
def list_complaints():
    """Өргөдөл, гомдлын жагсаалт. Шүүлт: ?search= &page= &per_page="""
    return _list("complaints")


@bp.route("/api/admin/complaints/<int:rid>", methods=["DELETE"])
def delete_complaint(rid):
    return _delete("complaints", rid)
