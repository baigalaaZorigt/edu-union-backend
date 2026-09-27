"""Порталын хайлт — ХАРАГДАХ контентын индекс, тааруулалт, эрэмбэ, snippet.

Индекс (corpus) нь порталд харагддаг бүх зүйлийн жагсаалт (dict бүр: type, id, title,
path, anchor, body, date):
  news      — status='published', deleted_at IS NULL; body = summary + текст блокууд
  page      — type='page' цэс, өөрөө болон эцэг нь is_visible=1, page.status='published';
              хуудас бүхэлдээ (anchor=None) + блок бүр (anchor="block-<id>")
  document  — хуудасны file блок (Хууль, журам г.м.) — хуудасны зам + anchor
  survey / poll — status <> 'draft', deleted_at IS NULL (порталын жагсаалттай ижил)
  partner   — is_visible=1; path нь байгууллагын URL

Тааруулалт SQL LIKE БИШ, Python-ийн `str.lower()` — SQLite-ийн LIKE/lower() кирилл
үсгийн том/жижгийг ялгадаг, Postgres-ийн LIKE бүр ялгадаг. Хэдэн мянган мөрөнд хангалттай
хурдан. Индексийг кэшилж, эх хүснэгтүүдийн мөрийн тоо + MAX(updated_at) (нэг хөнгөн
query) өөрчлөгдөх үед дахин барина — нийтэлсэн/устгасан контент тэр даруй харагдана.
updated_at секундийн нарийвчлалтай тул НЭГ секунд дотор хоёр удаа засвал хээ өөрчлөгдөхгүй
байж болно — тиймээс индекс CORPUS_MAX_AGE секундээс хуучин бол ямар ч байсан дахин баригдана.
LIKE ашиглахгүй тул wildcard шахах боломжгүй.
"""
import html
import re
import time

from sqlalchemy import func, select

from core.orm import session
from core.orm.models import Form, Menu, News, NewsBlock, Page, PageBlock, Partner

MIN_Q, MAX_Q = 2, 60
SNIPPET = 160
# Индекс барих эх хүснэгтүүд — эдгээрийн аль нэг өөрчлөгдвөл индекс дахин баригдана
CORPUS_MAX_AGE = 10                  # хээ ижил байсан ч үүнээс хуучин индексийг дахин барина
SOURCES = (News, NewsBlock, Menu, Page, PageBlock, Form, Partner)
TYPES = ("news", "page", "document", "survey", "poll", "partner")

_TAG = re.compile(r"<[^>]+>")
_HEADING = re.compile(r"<h[1-4][^>]*>(.*?)</h[1-4]>", re.I | re.S)
_SPACE = re.compile(r"\s+")

_corpus = {"sig": None, "at": 0.0, "docs": []}


def clean_q(raw):
    """q-г цэвэрлэнэ; 2–60 тэмдэгтээс гадуур бол None (-> хоосон хариу)."""
    q = _SPACE.sub(" ", (raw or "").strip())
    return q if MIN_Q <= len(q) <= MAX_Q else None


def plain(value):
    """HTML -> энгийн текст (tag хасаж, entity задалж, зай нэгтгэнэ)."""
    if not value:
        return ""
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", value))).strip()


def _date(value):
    return (value or "").replace("T", " ")[:19]


def _page_paths(menus):
    """Харагдах 'page' цэс бүрийн порталын зам: эцгүүдийн slug-аар ("/bidnii-tuhai/x")."""
    by_id = {m["id"]: m for m in menus}
    out = {}
    for m in menus:
        chain, cur, visible = [], m, True
        while cur is not None:
            visible = visible and bool(cur["is_visible"])
            chain.append(cur["slug"])
            cur = by_id.get(cur["parent_id"])
        if visible and m["type"] == "page":
            out[m["id"]] = "/" + "/".join(reversed(chain))
    return out


def _block_title(b):
    """Блокийн гарчиг: title/caption/name, эсвэл текст доторх эхний <h1-4>."""
    for f in ("title", "caption", "name"):
        if b[f]:
            return b[f].strip()
    m = _HEADING.search(b["text"] or "")
    return plain(m.group(1)) if m else None


def build_corpus(s):
    """Порталд харагдах бүх контентыг индекс болгоно (`s` — ORM session)."""
    docs = []
    blocks = {}
    for b in s.execute(select(NewsBlock.news_id, NewsBlock.text).where(NewsBlock.type == "text")
                       .order_by(NewsBlock.sort_order, NewsBlock.id)):
        blocks.setdefault(b.news_id, []).append(plain(b.text))
    for n in s.execute(select(News.id, News.title, News.summary, News.published_at,
                              News.created_at)
                       .where(News.status == "published", News.deleted_at.is_(None))):
        docs.append({"type": "news", "id": n.id, "title": n.title, "path": f"/news/{n.id}",
                     "anchor": None, "date": _date(n.published_at or n.created_at),
                     "body": " ".join([plain(n.summary)] + blocks.get(n.id, []))})

    paths = _page_paths(s.execute(select(Menu.id, Menu.parent_id, Menu.slug, Menu.type,
                                         Menu.is_visible)).mappings().all())
    pages = {}
    for p in s.execute(select(Page.id, Page.menu_id, Page.body, Page.updated_at, Menu.title)
                       .join(Menu, Menu.id == Page.menu_id).where(Page.status == "published")):
        if p.menu_id not in paths:
            continue
        pages[p.id] = p
        docs.append({"type": "page", "id": p.id, "title": p.title,
                     "path": paths[p.menu_id], "anchor": None,
                     "date": _date(p.updated_at), "body": plain(p.body)})
    for blk in s.scalars(select(PageBlock).order_by(PageBlock.sort_order, PageBlock.id)):
        p = pages.get(blk.page_id)
        if p is None:
            continue
        b = blk.to_dict()
        is_doc = b["type"] == "file"
        title = _block_title(b)
        if is_doc and not title:
            title = (b["url"] or "").rsplit("/", 1)[-1] or None
        docs.append({"type": "document" if is_doc else "page", "id": p.id,
                     "title": title, "path": paths[p.menu_id], "anchor": f"block-{b['id']}",
                     "date": _date(p.updated_at), "body": plain(b["text"]),
                     "page_title": p.title})

    for f in s.execute(select(Form.id, Form.type, Form.title, Form.description, Form.created_at)
                       .where(Form.status != "draft", Form.deleted_at.is_(None))):
        docs.append({"type": f.type, "id": f.id, "title": f.title,
                     "path": f"/{f.type}/{f.id}", "anchor": None,
                     "date": _date(f.created_at), "body": plain(f.description)})
    for p in s.execute(select(Partner.id, Partner.name, Partner.url, Partner.created_at)
                       .where(Partner.is_visible == 1)):
        docs.append({"type": "partner", "id": p.id, "title": p.name, "path": p.url,
                     "anchor": None, "date": _date(p.created_at), "body": ""})
    return docs


def _signature(s):
    """Эх хүснэгт бүрийн (мөрийн тоо, MAX(updated_at)) — өөрчлөлтийг илрүүлэх хурууны хээ.

    Нэмэх/устгах нь тоог, засах нь updated_at-ийг (timestamp trigger) өөрчилнө. Бүгдийг
    скаляр дэд query болгон НЭГ query-ээр авна.
    """
    parts = []
    for m in SOURCES:
        parts += [select(func.count()).select_from(m).scalar_subquery(),
                  select(func.max(m.updated_at)).scalar_subquery()]
    return tuple(s.execute(select(*parts)).one())


def corpus():
    """Кэшилсэн индекс; эх өгөгдөл өөрчлөгдсөн бол л DB-ээс дахин барина."""
    s = session()
    sig, now = _signature(s), time.monotonic()
    if sig != _corpus["sig"] or now - _corpus["at"] >= CORPUS_MAX_AGE:
        _corpus["docs"] = build_corpus(s)
        _corpus["sig"], _corpus["at"] = sig, now
    return _corpus["docs"]


def clear_cache():
    _corpus["sig"], _corpus["at"] = None, 0.0


def _newest_first(docs):
    return sorted(docs, key=lambda d: d["date"], reverse=True)


def suggest(q, limit):
    """Зөвхөн гарчгаар: эхэлж таарсан -> агуулсан -> шинэ нь эхэнд."""
    ql = q.lower()
    hits = [d for d in _newest_first(corpus()) if d["title"] and ql in d["title"].lower()]
    hits.sort(key=lambda d: 0 if d["title"].lower().startswith(ql) else 1)   # stable
    return [item(d) for d in hits[:limit]]


def search(q, type_=None):
    """Гарчиг + их бие: гарчгаар таарсан -> их биеэр таарсан -> шинэ нь эхэнд."""
    ql = q.lower()
    ranked = []
    for d in _newest_first(corpus()):
        if type_ and d["type"] != type_:
            continue
        # гарчиггүй блокийг хуудасны гарчгаар тааруулахгүй — нэг хуудас олон давхардахгүй
        title = (d["title"] or "").lower()
        if ql in title:
            ranked.append((0 if title.startswith(ql) else 1, d))
        elif ql in d["body"].lower():
            ranked.append((2, d))
    ranked.sort(key=lambda r: r[0])
    return [dict(item(d, title_fallback=True), snippet=snippet(d["body"], q)) for _, d in ranked]


def item(d, title_fallback=False):
    title = d["title"] or (d.get("page_title") if title_fallback else None)
    return {"type": d["type"], "id": d["id"], "title": title, "path": d["path"],
            "anchor": d["anchor"]}


def snippet(body, q):
    """Эхний таарсан газрын орчмын ~160 тэмдэгт; HTML escape хийгээд таарсныг <mark>."""
    if not body:
        return ""
    low, ql = body.lower(), q.lower()
    pos = low.find(ql)
    start = 0 if pos < 0 else max(0, pos - (SNIPPET - len(q)) // 2)
    end = min(len(body), start + SNIPPET)
    start = max(0, end - SNIPPET)
    part = body[start:end]
    out, i, pl = [], 0, part.lower()
    while True:
        j = pl.find(ql, i)
        if j < 0:
            out.append(html.escape(part[i:]))
            break
        out.append(html.escape(part[i:j]) + "<mark>" + html.escape(part[j:j + len(q)]) + "</mark>")
        i = j + len(q)
    return ("…" if start > 0 else "") + "".join(out) + ("…" if end < len(body) else "")
