"""Порталын контентын (цэс, хуудас, блок) хариу хэлбэржүүлэлт — admin ба client хуваалцана.

admin/content/* (токен + эрх) болон client/content.py (/api/portal/... — токенгүй) хоёулаа
эндээс авдаг тул хоёр талын хариу ЯГ ижил хэлбэртэй. Портал зөвхөн харагдах цэс,
нийтлэгдсэн хуудсыг л харуулна — `visible_menu_ids()` / `public_page_ids()`.
"""
from sqlalchemy import false, select

from core.orm import session
from core.orm.models import Menu, Page, PageBlock

# Блокийн төрөл -> тухайн төрөлд хамаарах талбарууд (бусад багана NULL үлдэнэ)
BLOCK_FIELDS = {
    "text":  ("text",),
    "image": ("url", "caption"),
    "video": ("url", "title"),
    "file":  ("url", "name", "mime_type", "size"),
    "link":  ("url", "title"),
}
BLOCK_TYPES = tuple(BLOCK_FIELDS)

# ?tree= / ?is_visible= зэрэг query-д "үнэн" гэж тооцох утгууд
TRUE_ARGS = ("1", "true", "True")

MENU_SELECT = select(Menu, Page.id.label("page_id")).outerjoin(Page, Page.menu_id == Menu.id)
MENU_ORDER = (Menu.parent_id.is_not(None), Menu.parent_id, Menu.sort_order, Menu.id)
BLOCK_ORDER = (PageBlock.page_id, PageBlock.sort_order, PageBlock.id)


def eq_arg(column, value):
    """Query string-ийн утгаар тоон баганыг шүүх нөхцөл (тоо биш бол юу ч таарахгүй)."""
    return column == int(value) if str(value).isdigit() else false()


def public_block(block):
    """Блокийг төрөлдөө хамаарах талбаруудаар нь цэвэрхэн буцаана."""
    out = {"id": block.id, "page_id": block.page_id,
           "type": block.type, "sort_order": block.sort_order,
           "created_at": block.created_at, "updated_at": block.updated_at}
    for f in BLOCK_FIELDS.get(block.type, ()):
        out[f] = getattr(block, f)
    if block.type == "video":
        out["youtube_url"] = block.url      # спекийн нэршил
    return out


def blocks_of(page_id, btype=None):
    """Хуудасны блокуудыг эрэмбээр нь (сонголтоор нэг төрлөөр шүүж) буцаана."""
    stmt = select(PageBlock).where(PageBlock.page_id == page_id)
    if btype:
        stmt = stmt.where(PageBlock.type == btype)
    return [public_block(b) for b in
            session().scalars(stmt.order_by(PageBlock.sort_order, PageBlock.id))]


def menu_dict(row):
    """(Menu, page_id) мөрийг хуучин `m.*, page_id` dict болгоно."""
    return dict(row["Menu"].to_dict(), page_id=row["page_id"])


def tree(flat):
    """Хавтгай жагсаалтыг эцэг-хүүхдийн мод болгоно (children түлхүүртэйгээр)."""
    by_id = {r["id"]: dict(r, children=[]) for r in flat}
    roots = []
    for r in flat:
        node = by_id[r["id"]]
        parent = by_id.get(r["parent_id"])
        (parent["children"] if parent else roots).append(node)
    return roots


def menu_filters(stmt, args, public=False):
    """GET /menu-ийн шүүлтүүд (?parent_id=, ?type=, ?is_visible=) + эрэмбэ.

    public=True: ?is_visible-ийг үл хайхарч ЗӨВХӨН харагдах цэсүүд (эцгүүд нь ч харагдах).
    """
    parent_id = args.get("parent_id")
    if parent_id is not None:
        if parent_id in ("", "null", "0"):
            stmt = stmt.where(Menu.parent_id.is_(None))
        else:
            stmt = stmt.where(eq_arg(Menu.parent_id, parent_id))
    if args.get("type"):
        stmt = stmt.where(Menu.type == args["type"])
    if public:
        stmt = stmt.where(Menu.id.in_(visible_menu_ids()))
    elif args.get("is_visible") is not None:
        stmt = stmt.where(Menu.is_visible == (1 if args["is_visible"] in TRUE_ARGS else 0))
    return stmt.order_by(*MENU_ORDER)


def page_payload(page):
    """GET /page/<menu_id>-ийн хариу: хуудас + blocks + images/files/videos."""
    data = dict(page.to_dict(), blocks=blocks_of(page.id))
    for key, btype in (("images", "image"), ("files", "file"), ("videos", "video")):
        data[key] = blocks_of(page.id, btype)
    return data


def visible_menu_ids():
    """Өөрөө болон бүх эцэг нь is_visible=1 цэсүүдийн id (порталд харагдах)."""
    rows = session().execute(select(Menu.id, Menu.parent_id, Menu.is_visible)).all()
    by_id = {r.id: r for r in rows}
    out = set()
    for r in rows:
        cur, ok, seen = r, True, set()
        while cur is not None and cur.id not in seen:
            seen.add(cur.id)
            ok = ok and bool(cur.is_visible)
            cur = by_id.get(cur.parent_id)
        if ok:
            out.add(r.id)
    return out


def public_page_ids():
    """Порталд харагдах хуудсууд: нийтлэгдсэн (published) + цэс нь харагдах."""
    return set(session().scalars(select(Page.id).where(
        Page.status == "published", Page.menu_id.in_(visible_menu_ids()))))
