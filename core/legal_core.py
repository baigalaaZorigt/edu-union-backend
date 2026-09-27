"""Хууль тогтоомжийн домэйний цөм — admin/legal.py ба client/legal.py хуваалцана.

display_mode нь порталын мөр юу хийхийг заана:
  link   — «Үзэх»: external_url (заавал, http(s)://) шинэ табд
  file   — «Татах»: pdf_url (заавал) шууд
  detail — «Дэлгэрэнгүй үзэх»: legal_document_block-оос бүтсэн хуудас; pdf_url байвал дээд
           талд үндсэн баримт болж харагдана (заавал биш)
Блок: page_block / news_block-той ижил хэлбэр, гэхдээ text / file / link л.
"""
import datetime as dt
import re

from flask import abort

DISPLAY_MODES = ("link", "file", "detail")
DOC_FIELDS = ("title", "category", "published_date", "source_name", "display_mode",
              "external_url", "pdf_url", "sort_order", "is_visible")
PUBLIC_FIELDS = ("id", "title", "category", "published_date", "source_name", "display_mode",
                 "external_url", "pdf_url")
BLOCK_FIELDS = {"text": ("text",), "file": ("url", "name", "mime_type", "size"),
                "link": ("url", "title")}
BLOCK_TYPES = tuple(BLOCK_FIELDS)
MAX_TEXT = 500
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


def bad(message, code=400):
    abort(code, description=message)


def _text(value, field, required=False, max_len=MAX_TEXT):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            bad(f"{field} заавал шаардлагатай")
        return None
    if not isinstance(value, str):
        bad(f"{field} нь текст байх ёстой")
    value = value.strip()
    if len(value) > max_len:
        bad(f"{field} хэт урт (дээд тал нь {max_len} тэмдэгт)")
    return value


def _http(value):
    return value.lower().startswith(("http://", "https://"))


def _url(value, field):
    """http(s):// эсвэл харьцангуй зам (/uploads/...); javascript: болон //host хориотой."""
    value = _text(value, field, max_len=2000)
    if value is None or _http(value):
        return value
    if _SCHEME.match(value) or value.startswith("//"):
        bad(f"{field} нь http(s):// эсвэл харьцангуй зам байх ёстой")
    return value


def _date(value):
    """'YYYY-MM-DD' (эсвэл портал шиг 'YYYY.MM.DD') -> 'YYYY-MM-DD'."""
    value = _text(value, "published_date", max_len=10)
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value.replace(".", "-")).isoformat()
    except ValueError:
        bad("published_date буруу огноо (ж: 2021-07-02)")


def _int(value, field):
    if isinstance(value, bool):
        bad(f"{field} нь бүхэл тоо байх ёстой")
    try:
        return int(value)
    except (TypeError, ValueError):
        bad(f"{field} нь бүхэл тоо байх ёстой")


def _flag(value, field):
    if value in (True, 1, "1", "true", "True"):
        return 1
    if value in (False, 0, "0", "false", "False"):
        return 0
    bad(f"{field} нь true/false байх ёстой")


def validate_document(data, current=None):
    """Ирсэн талбаруудыг шалгаж хадгалах утгуудыг буцаана.

    current (засах үед одоогийн мөрийн dict) — хэсэгчилсэн PUT/PATCH-ийн дараах НИЙЛМЭЛ
    төлөвөөр display_mode-ийн шаардлагыг шалгана.
    """
    out = {}
    if "title" in data or current is None:
        out["title"] = _text(data.get("title"), "title", required=True)
    for f, n in (("category", 100), ("source_name", 200)):
        if f in data:
            out[f] = _text(data[f], f, max_len=n)
    if "published_date" in data:
        out["published_date"] = _date(data["published_date"])
    if "display_mode" in data or current is None:
        mode = data.get("display_mode")
        if mode not in DISPLAY_MODES:
            bad("display_mode буруу. Сонголт: " + ", ".join(DISPLAY_MODES))
        out["display_mode"] = mode
    for f in ("external_url", "pdf_url"):
        if f in data:
            out[f] = _url(data[f], f)
    if "sort_order" in data:
        out["sort_order"] = _int(data["sort_order"], "sort_order")
    if "is_visible" in data:
        out["is_visible"] = _flag(data["is_visible"], "is_visible")

    merged = {**(current or {}), **out}
    if merged["display_mode"] == "link":
        if not merged.get("external_url"):
            bad("display_mode='link' үед external_url заавал")
        if not _http(merged["external_url"]):
            bad("external_url нь http:// эсвэл https://-ээр эхлэх ёстой")
    if merged["display_mode"] == "file" and not merged.get("pdf_url"):
        bad("display_mode='file' үед pdf_url заавал")
    return out


def validate_block(data, current_type=None):
    """Блокийн төрөл ба талбарууд — (type, утгууд). Засах үед төрлийг солихгүй."""
    btype = current_type or data.get("type")
    if btype not in BLOCK_TYPES:
        bad("type буруу. Сонголт: " + ", ".join(BLOCK_TYPES))
    out = {}
    for f in BLOCK_FIELDS[btype]:
        if f not in data and current_type:
            continue
        if f == "size":
            out[f] = None if data.get(f) in (None, "") else _int(data[f], f)
        elif f == "url":
            out[f] = _url(data.get(f), f)
        elif f == "text":
            if data.get(f) is not None and not isinstance(data[f], str):
                bad("text нь текст байх ёстой")
            out[f] = data.get(f)
        else:
            out[f] = _text(data.get(f), f)
    if "sort_order" in data:
        out["sort_order"] = _int(data["sort_order"], "sort_order")
    if btype != "text" and not current_type and not out.get("url"):
        bad(f"type='{btype}' үед url заавал")
    return btype, out


def admin_document(doc):
    out = doc.to_dict()
    out["is_visible"] = bool(out["is_visible"])
    return out


def public_document(doc):
    return {f: getattr(doc, f) for f in PUBLIC_FIELDS}


def public_block(block):
    """Блок — зөвхөн тухайн төрлийн талбарууд (page_block / news_block-той ижил зарчим)."""
    out = {"id": block.id, "legal_document_id": block.legal_document_id,
           "type": block.type, "sort_order": block.sort_order}
    out.update({f: getattr(block, f) for f in BLOCK_FIELDS.get(block.type, ())})
    return out
