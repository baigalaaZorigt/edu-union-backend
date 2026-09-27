"""menu (Цэс) — порталын 2 түвшний динамик цэс: CRUD, reorder, slug."""

from flask import jsonify, request, abort
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.helpers import require, json_body, list_json
from core.orm import session
from core.orm.models import Menu, Page, PageBlock
from core.orm.query import paginate

from admin.content import bp
from admin.content.storage import remove_upload
from admin.content.common import _TRUE, _ensure_page, _eq_arg, _next_sort, _now, _order_items


# Цэсний төрлүүд (спекийн хүснэгт). page-аас бусад нь кодод суусан функциональ хуудас.
MENU_TYPES = ("page", "news", "survey", "poll", "contact", "home", "external")

# Цэсний засаж/оруулж болох талбарууд (slug тусад нь боловсруулагдана)
MENU_FIELDS = ("parent_id", "title", "type", "sort_order", "is_visible", "external_url",
               "news_category")

# type='news' цэс аль ангиллын мэдээг харуулахыг заана (news_core-той ижил жагсаалт).
# NULL = бүх ангилал (хуучин цэсүүд ингэж ажиллана).
NEWS_CATEGORIES = ("Мэдээ", "Сургалт")

# Кирилл -> латин галиглал (slug автоматаар үүсгэхэд)
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ү": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _slugify(text):
    """Гарчгаас URL-д тохирох slug гаргана (кирилл үсгийг галиглана)."""
    out = []
    for ch in (text or "").strip().lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append("-")
    slug = "-".join(part for part in "".join(out).split("-") if part)
    return slug[:80]


def _unique_slug(base, mid=None):
    """Давхцахгүй slug буцаана — давхцвал -2, -3 ... гэж дугаарлана."""
    base = base or "menu"
    slug, n = base, 1
    while True:
        found = session().scalar(select(Menu.id).where(Menu.slug == slug))
        if found is None or found == mid:
            return slug
        n += 1
        slug = f"{base}-{n}"


def _check_parent(parent_id, mid=None):
    """Эцэг цэс зөв эсэхийг шалгана: байгаа, өөрөө биш, гүн 2 түвшнээс хэтрэхгүй."""
    if parent_id in (None, "", 0):
        return None
    try:
        parent_id = int(parent_id)
    except (TypeError, ValueError):
        abort(400, description="parent_id тоо байх ёстой")
    if mid is not None and parent_id == mid:
        abort(400, description="Цэс өөрийгөө эцэг болгож болохгүй")
    parent = session().get(Menu, parent_id)
    if parent is None:
        abort(400, description="parent_id (эцэг цэс) олдсонгүй")
    if parent.parent_id is not None:
        abort(400, description="Гүн 2 түвшин — дэд цэсний дэд цэс үүсгэхгүй")
    if mid is not None and session().scalar(
            select(Menu.id).where(Menu.parent_id == mid).limit(1)) is not None:
        abort(400, description="Дэд цэстэй цэсийг өөр цэсний доор оруулж болохгүй")
    return parent_id


def _validate_menu(data, current=None):
    """type / is_visible / external_url-г шалгана (буруу бол 400)."""
    mtype = data.get("type") or (current.type if current else None)
    if mtype and mtype not in MENU_TYPES:
        abort(400, description="type буруу. Сонголт: " + ", ".join(MENU_TYPES))
    if mtype == "external" and not data.get(
            "external_url", current.external_url if current else None):
        abort(400, description="type='external' үед external_url заавал")
    if data.get("news_category"):
        if mtype != "news":
            abort(400, description="news_category зөвхөн type='news' цэсэнд хамаарна")
        if data["news_category"] not in NEWS_CATEGORIES:
            abort(400, description="news_category буруу. Сонголт: "
                  + ", ".join(NEWS_CATEGORIES) + " (эсвэл хоосон = бүгд)")
    return mtype


# Цэсийг page_id-тай нь хамт унших select (админ UI шууд хуудсыг нь нээхэд)
MENU_SELECT = select(Menu, Page.id.label("page_id")).outerjoin(Page, Page.menu_id == Menu.id)


def _menu_dict(row):
    """(Menu, page_id) мөрийг хуучин `m.*, page_id` dict болгоно."""
    return dict(row["Menu"].to_dict(), page_id=row["page_id"])


def _menu_row(mid):
    """Цэсийг page_id-тай нь хамт буцаана (байхгүй бол None)."""
    row = session().execute(MENU_SELECT.where(Menu.id == mid)).mappings().first()
    return _menu_dict(row) if row else None


def _tree(flat):
    """Хавтгай жагсаалтыг эцэг-хүүхдийн мод болгоно (children түлхүүртэйгээр)."""
    by_id = {r["id"]: dict(r, children=[]) for r in flat}
    roots = []
    for r in flat:
        node = by_id[r["id"]]
        parent = by_id.get(r["parent_id"])
        (parent["children"] if parent else roots).append(node)
    return roots


def _subtree_ids(mid):
    """Цэс ба түүний бүх удам (дэд цэсүүд)-ын id — Python-оор давхарга давхаргаар."""
    ids, frontier = [mid], [mid]
    while frontier:
        frontier = list(session().scalars(select(Menu.id).where(Menu.parent_id.in_(frontier))))
        ids += frontier
    return ids


# ============================ menu (Цэс) ============================
@bp.route("/api/menu", methods=["GET"])
def list_menu():
    """Бүх цэс. ?tree=1 -> мод хэлбэрээр, эс бөгөөс parent_id-тай хавтгай жагсаалт.

    Шүүлт: ?parent_id= (root бол 'null'), ?type=, ?is_visible=1
    """
    stmt = MENU_SELECT
    parent_id = request.args.get("parent_id")
    if parent_id is not None:
        if parent_id in ("", "null", "0"):
            stmt = stmt.where(Menu.parent_id.is_(None))
        else:
            stmt = stmt.where(_eq_arg(Menu.parent_id, parent_id))
    if request.args.get("type"):
        stmt = stmt.where(Menu.type == request.args["type"])
    if request.args.get("is_visible") is not None:
        stmt = stmt.where(Menu.is_visible == (1 if request.args["is_visible"] in _TRUE else 0))
    stmt = stmt.order_by(Menu.parent_id.is_not(None), Menu.parent_id, Menu.sort_order, Menu.id)
    if request.args.get("tree") in _TRUE:     # мод бүтэн байх ёстой — хуудаслахгүй
        rows = session().execute(stmt).mappings().all()
        return jsonify(_tree([_menu_dict(r) for r in rows]))
    rows, meta = paginate(stmt, mappings=True)
    return list_json([_menu_dict(r) for r in rows], meta)


@bp.route("/api/menu/<int:mid>", methods=["GET"])
def get_menu(mid):
    row = _menu_row(mid)
    if row is None:
        abort(404, description="Цэс олдсонгүй")
    return jsonify(row)


def _flush_or_409():
    """Нэмэх/засахыг DB руу илгээнэ — slug давхцвал (UNIQUE) 409."""
    s = session()
    try:
        s.flush()
    except IntegrityError:
        s.rollback()
        abort(409, description="Энэ slug аль хэдийн бүртгэгдсэн байна")


@bp.route("/api/menu", methods=["POST"])
def create_menu():
    """Цэс нэмэх. slug байхгүй бол гарчгаас автоматаар үүснэ.

    type='page' үед хоосон page бичлэг дагаад үүснэ.
    """
    data = request.get_json(silent=True)
    require(data, ["title"])
    mtype = _validate_menu(data) or "page"
    parent_id = _check_parent(data.get("parent_id"))
    now = _now()
    menu = Menu(
        parent_id=parent_id, title=data["title"],
        slug=_unique_slug(_slugify(data.get("slug") or data["title"])),
        type=mtype,
        sort_order=data.get("sort_order") or _next_sort(Menu.parent_id, parent_id),
        is_visible=1 if data.get("is_visible", True) else 0,
        external_url=data.get("external_url"),
        news_category=data.get("news_category") or None,
        created_at=now, updated_at=now)
    session().add(menu)
    _flush_or_409()
    if mtype == "page":
        _ensure_page(menu.id, data["title"])
    session().commit()
    return jsonify(_menu_row(menu.id)), 201


@bp.route("/api/menu/reorder", methods=["PUT", "PATCH"])
def reorder_menu():
    """Drag-drop эрэмбийг бүхэлд нь хадгална.

    body: {"order": [{"id": 5, "parent_id": null, "sort_order": 1}, ...]}
    """
    items = _order_items(Menu, "Цэс")
    updates = [(menu, item.get("parent_id"), item.get("sort_order", 0)) for menu, item in items]
    # Эцэг солигдох бол гүний шалгалт — бүх мөр DB дээр байгаа нь батлагдсаны дараа.
    for menu, parent_id, _ in updates:
        _check_parent(parent_id, menu.id)
    now = _now()
    for menu, parent_id, sort_order in updates:
        menu.parent_id, menu.sort_order, menu.updated_at = parent_id or None, sort_order, now
    ids = [m.id for m, _, _ in updates]
    session().commit()
    return jsonify(updated=ids)


@bp.route("/api/menu/<int:mid>", methods=["PUT", "PATCH"])
def update_menu(mid):
    """Цэс засах. type='page' болгож өөрчилвөл дутуу page бичлэг нөхөгдөнө."""
    data = json_body()
    current = session().get(Menu, mid)
    if current is None:
        abort(404, description="Цэс олдсонгүй")
    mtype = _validate_menu(data, current)
    values = {}
    for f in MENU_FIELDS:
        if f not in data:
            continue
        val = data[f]
        if f == "parent_id":
            val = _check_parent(val, mid)
        elif f == "is_visible":
            val = 1 if val else 0
        elif f == "news_category":
            val = val or None       # хоосон = бүх ангилал
        values[f] = val
    if "slug" in data or "title" in data:
        base = _slugify(data.get("slug") or data.get("title"))
        values["slug"] = _unique_slug(base, mid)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    values["updated_at"] = _now()
    old_title = current.title
    for f, v in values.items():
        setattr(current, f, v)
    _flush_or_409()
    if mtype == "page":
        _ensure_page(mid, data.get("title") or old_title)
    session().commit()
    return jsonify(_menu_row(mid))


@bp.route("/api/menu/<int:mid>", methods=["DELETE"])
def delete_menu(mid):
    """Цэс устгах — дэд цэс, page, блокууд нь бүгд хамт устна (cascade)."""
    s = session()
    menu = s.get(Menu, mid)
    if menu is None:
        abort(404, description="Цэс олдсонгүй")
    # Устахаас өмнө диск дээрх файлуудынх нь URL-г цуглуулна (дэд цэсийг оруулаад).
    pages = select(Page.id).where(Page.menu_id.in_(_subtree_ids(mid)))
    urls = list(s.scalars(select(PageBlock.url).where(
        PageBlock.page_id.in_(pages), PageBlock.url.is_not(None))))
    urls += list(s.scalars(select(Page.cover_image).where(
        Page.id.in_(pages), Page.cover_image.is_not(None))))
    s.delete(menu)            # дэд цэс, page, блокууд — DB-ийн ON DELETE CASCADE
    s.commit()
    for url in urls:
        remove_upload(url)
    return jsonify(deleted=mid)
