"""Санал хүсэлт, Өргөдөл гомдлын АДМИН тал (Blueprint).

Замын угтвар: /api/admin/... — жагсаалт (хайлт + хуудаслалт) ба устгал.
Порталын тал (маягт илгээх, токенгүй) нь client/feedback.py дотор.

**"Нэгийг авах" маршрут байхгүй** (спек §4): жагсаалтын хариунд message /
description хамт бүрэн ирдэг тул админы 👁 дэлгэрэнгүй модаль нь татсан
датагаа шууд харуулна.

**Төлөв солих маршрут ч байхгүй**: `status` багана `'new'` хэвээр байна —
V1-д UI үүнийг ашиглахгүй тул спек зориуд орхисон (§2).
"""
from flask import Blueprint, abort, jsonify, request

from core.feedback_core import KINDS, list_page
from core.orm import session

bp = Blueprint("admin_feedback", __name__)


def _list(kind):
    return jsonify(list_page(kind, request.args))


def _delete(kind, rid):
    """Мөрийг устгана; өргөдлийн хавсралт байвал дискнээс нь ч арилгана."""
    spec = KINDS[kind]
    s = session()
    row = s.get(spec["model"], rid)
    if row is None:
        abort(404, description=spec["label"] + " олдсонгүй")
    s.delete(row)                           # soft delete — хавсралт файл хадгалагдана
    s.commit()
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
