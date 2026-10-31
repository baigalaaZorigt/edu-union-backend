"""Жагсаалтын server-side хайлт / шүүлт / эрэмбэ / хуудаслалт — server_list_api_spec.md.

`GET /api/user`, `/api/member`, `/api/organization` (Excel экспорт ч мөн адил query-г авна):

    ?search=      — ListSpec.search-ийн бүх талбараас OR (том/жижиг үсэг үл ялгах, хэсэгчлэн)
    ?<багана>=    — ListSpec.filters (хоосон утга -> шүүлтгүй); бүх нөхцөл AND, scope-той хамт
    ?sort=&order= — ListSpec.sort whitelist (анхдагч created_at desc) + id ижил чиглэлээр
    ?page=&per_page= — {items, page, pages, per_page, total}; хоёулаа байхгүй бол массив

Буруу sort / order / тоо биш page·per_page·int шүүлт -> 422 {"error", "message"}.
Текстийг ci_lower()-оор (Кирилл зөв) тааруулж, `%` `_`-г autoescape хийнэ — SQL-д баганын
нэр хэзээ ч хэрэглэгчээс орохгүй (зөвхөн whitelist map).
"""
from flask import request
from sqlalchemy import asc, desc, func, or_, select
from werkzeug.exceptions import UnprocessableEntity

from core.helpers import MAX_PER_PAGE
from core.orm import session
from core.orm.ci import ci_lower

DEFAULT_PER_PAGE = 10
DEFAULT_SORT = "created_at"


class BadParam(UnprocessableEntity):
    def __init__(self, message):
        super().__init__(description=message)
        self.extra = {"message": message}


class ListSpec:
    """search: [утга -> нөхцөл]; filters: {параметр: утга -> нөхцөл};
    sort: {параметр: [багана...] эсвэл stmt -> (stmt, [багана...])}; id: tie-break багана."""

    def __init__(self, id, search, filters, sort):
        self.id, self.search, self.filters, self.sort = id, search, filters, sort


# ------------------------------ нөхцөл бүтээгчид ------------------------------
def contains(expr):
    """Текст: том/жижиг үсэг үл ялгах, хэсэгчлэн (LIKE %x%, % _ escape)."""
    return lambda v: ci_lower(expr).contains(v.lower(), autoescape=True)


def equals(expr):
    return lambda v: expr == v


def as_int(value, name):
    try:
        return int(value)
    except ValueError:
        raise BadParam(f"{name} нь бүхэл тоо байх ёстой") from None


def int_equals(expr, name):
    return lambda v: expr == as_int(v, name)


def full_name(model):
    """'Овог Нэр' — хайлтад (NULL-ийг хоосон болгоно)."""
    return func.coalesce(model.last_name, "").concat(" ").concat(func.coalesce(model.first_name, ""))


# ------------------------------ хэрэглэх ------------------------------
def _sort_params(spec):
    sort = request.args.get("sort") or DEFAULT_SORT
    if sort not in spec.sort:
        raise BadParam("Буруу sort талбар")
    order = (request.args.get("order") or "desc").lower()
    if order not in ("asc", "desc"):
        raise BadParam("Буруу order утга (asc | desc)")
    return sort, order


def apply(stmt, spec):
    """stmt-д search + баганын шүүлт (WHERE) ба эрэмбэ (ORDER BY ... , id) нэмнэ."""
    args = request.args
    q = (args.get("search") or "").strip()
    if q:
        stmt = stmt.where(or_(*(f(q) for f in spec.search)))
    for name, f in spec.filters.items():
        v = (args.get(name) or "").strip()
        if v:
            stmt = stmt.where(f(v))
    sort, order = _sort_params(spec)
    cols = spec.sort[sort]
    if callable(cols):
        stmt, cols = cols(stmt)
    d = desc if order == "desc" else asc
    return stmt.order_by(*(d(c).nulls_last() for c in cols), d(spec.id))


def _page_params():
    args = request.args
    if args.get("page") in (None, "") and args.get("per_page") in (None, ""):
        return None
    page = max(1, as_int(args.get("page") or "1", "page"))
    per_page = min(MAX_PER_PAGE, max(1, as_int(args.get("per_page") or str(DEFAULT_PER_PAGE),
                                               "per_page")))
    return page, per_page


def paginate(stmt):
    """apply()-сан select -> (mapping мөрүүд, meta | None). total нь ижил WHERE-ээр."""
    s = session()
    pp = _page_params()
    if pp is None:
        return s.execute(stmt).mappings().all(), None
    page, per_page = pp
    total = s.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = s.execute(stmt.limit(per_page).offset((page - 1) * per_page)).mappings().all()
    return items, {"total": total, "page": page, "per_page": per_page,
                   "pages": max(1, (total + per_page - 1) // per_page)}

