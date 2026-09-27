"""ORM query-ийн хуваалцсан туслахууд: хуудаслалт, "олдохгүй бол 404"."""
from flask import abort
from sqlalchemy import func, select

from core.helpers import page_params
from core.orm import session


def paginate(stmt, mappings=False):
    """select()-ийг (хүссэн бол) хуудаслана -> (мөрүүд, meta | None).

    ?page= / ?per_page= өгөөгүй бол бүх мөр, meta=None (core.helpers.list_json массив буцаана).
    mappings=False: model объектууд (scalars); True: олон баганатай select-ийн dict-мөрүүд.
    COUNT нь ORDER BY-гүй дэд query дээр — ижил шүүлт, ижил тоо.
    """
    s = session()

    def run(q):
        res = s.execute(q)
        return res.mappings().all() if mappings else res.scalars().all()

    pp = page_params()
    if pp is None:
        return run(stmt), None
    page, per_page = pp
    total = s.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = run(stmt.limit(per_page).offset((page - 1) * per_page))
    return items, {"total": total, "page": page, "per_page": per_page,
                   "pages": (total + per_page - 1) // per_page}


def get_or_404(model, key, message):
    """Анхдагч түлхүүрээр нэг мөр — байхгүй бол 404 `message`."""
    obj = session().get(model, key)
    if obj is None:
        abort(404, description=message)
    return obj
