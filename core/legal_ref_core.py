"""Эрх зүй (legal_reference) — дугаарласан модны шалгалт ба хариуны хэлбэр (хоёр site).

Мөр бүр `parent_id` (NULL = дээд түвшний хэсэг) + `sort_order`-той; "1", "1.1", "1.1.1"
дугаар ХАДГАЛАГДАХГҮЙ — frontend модны байрлалаас бодно. `url`-тай мөр гадаад сайт руу
(legalinfo.mn) үсэрнэ, `url`-гүй нь дэд мөрүүдээ агуулсан бүлгийн гарчиг. Гүнд хязгааргүй.
"""
from flask import abort
from sqlalchemy import func, select

from core.orm import session
from core.orm.models import LegalReference

FIELDS = ("parent_id", "title", "url", "sort_order", "is_visible")
NOT_FOUND = "Эрх зүйн мөр олдсонгүй"


def bad(message):
    abort(400, description=message)


def admin_row(obj):
    out = obj.to_dict()
    out.pop("deleted_at", None)
    out["is_visible"] = bool(out["is_visible"])
    return out


def public_row(obj):
    return {f: getattr(obj, f) for f in ("id", "parent_id", "title", "url", "sort_order")}


def _int(value, field):
    if isinstance(value, bool) or not str(value).strip().lstrip("-").isdigit():
        bad(f"{field} нь бүхэл тоо байх ёстой")
    return int(value)


def _check_parent(parent_id, current):
    """Эцэг мөр байгаа эсэх; өөрөө эсвэл өөрийн удам эцэг болохгүй (цикл)."""
    s = session()
    seen, cur = set(), parent_id
    while cur is not None:
        if current is not None and cur == current["id"]:
            bad("parent_id: мөр өөрөө эсвэл өөрийн дэд мөр эцэг болохгүй")
        row = s.get(LegalReference, cur)
        if row is None or cur in seen:
            bad("parent_id (эцэг мөр) олдсонгүй")
        seen.add(cur)
        cur = row.parent_id


def next_sort_order(parent_id):
    """Ах дүүсийн төгсгөлд — sort_order өгөөгүй шинэ мөрийн байрлал."""
    cond = (LegalReference.parent_id.is_(None) if parent_id is None
            else LegalReference.parent_id == parent_id)
    return (session().scalar(select(func.max(LegalReference.sort_order)).where(cond)) or 0) + 1


def validate(data, current=None):
    """Хүсэлтийн биеэс хадгалах утгуудыг гаргана (current өгвөл хэсэгчилсэн засвар)."""
    values = {}
    if "parent_id" in data:
        pid = data["parent_id"]
        values["parent_id"] = None if pid in (None, "") else _int(pid, "parent_id")
        _check_parent(values["parent_id"], current)
    if "title" in data or current is None:
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            bad("title (гарчиг) заавал")
        values["title"] = title.strip()
    if "url" in data:
        url = data["url"]
        if url is not None and not isinstance(url, str):
            bad("url нь текст байх ёстой")
        url = (url or "").strip() or None
        if url is not None and not url.lower().startswith(("http://", "https://")):
            bad("url нь http:// эсвэл https://-ээр эхэлнэ")
        values["url"] = url
    if data.get("sort_order") is not None:
        values["sort_order"] = _int(data["sort_order"], "sort_order")
    elif current is None:
        values["sort_order"] = next_sort_order(values.get("parent_id"))
    if "is_visible" in data:
        values["is_visible"] = 1 if data["is_visible"] else 0
    return values


def ordered(rows):
    return sorted(rows, key=lambda r: (r.sort_order, r.id))


def visible_rows(s=None):
    """Порталд гарах мөрүүд: өөрөө БОЛОН дээшээ бүх эцэг нь is_visible (хэсгийг нуувал
    доторх бүх зүйл нуугдана)."""
    rows = (s or session()).scalars(select(LegalReference)).all()
    by_id = {r.id: r for r in rows}

    def shown(r, depth=0):
        if not r.is_visible or depth > len(rows):
            return False
        if r.parent_id is None:
            return True
        parent = by_id.get(r.parent_id)
        return parent is not None and shown(parent, depth + 1)

    return ordered([r for r in rows if shown(r)])
