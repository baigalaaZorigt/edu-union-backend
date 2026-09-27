"""page (Контент хуудас) — type='page' цэс бүрд нэг бичлэг."""

from flask import abort, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.helpers import require, json_body, pick, list_json
from core.orm import session
from core.orm.models import Menu, Page
from core.orm.query import paginate
from core.content_core import page_payload

from admin.content import bp
from core.content_storage import remove_upload
from admin.content.common import _now


# Хуудасны засаж болох талбарууд
PAGE_FIELDS = ("title", "body", "cover_image", "status")
PAGE_STATUSES = ("published", "draft")


# ======================= page (Контент хуудас) =======================
@bp.route("/api/page/<int:menu_id>", methods=["GET"])
def get_page(menu_id):
    """Тухайн ЦЭСНИЙ контентыг блок/зураг/файл/видеотой нь буцаана.

    Анхаар: спекийн дагуу GET нь menu_id-аар, PUT нь page id-аар ажиллана.
    """
    page = session().scalar(select(Page).where(Page.menu_id == menu_id))
    if page is None:
        abort(404, description="Энэ цэсэнд контент хуудас алга")
    return jsonify(page_payload(page))


@bp.route("/api/page", methods=["GET"])
def list_page():
    """Бүх контент хуудас (цэсний нэртэй нь). Админ жагсаалтад зориулав."""
    stmt = (select(Page, Menu.title.label("menu_title"), Menu.slug.label("menu_slug"))
            .join(Menu, Menu.id == Page.menu_id).order_by(Page.id))
    rows, meta = paginate(stmt, mappings=True)
    return list_json([dict(r["Page"].to_dict(), menu_title=r["menu_title"],
                           menu_slug=r["menu_slug"]) for r in rows], meta)


def _validate_page(data):
    status = data.get("status")
    if status and status not in PAGE_STATUSES:
        abort(400, description="status буруу. Сонголт: " + ", ".join(PAGE_STATUSES))


@bp.route("/api/page", methods=["POST"])
def create_page():
    """Цэсэнд контент хуудас үүсгэх (type='page' цэсэнд нэг л удаа)."""
    data = request.get_json(silent=True)
    require(data, ["menu_id"])
    _validate_page(data)
    s = session()
    menu = s.get(Menu, data["menu_id"]) if str(data["menu_id"]).isdigit() else None
    if menu is None:
        abort(400, description="menu_id (цэс) олдсонгүй")
    if menu.type != "page":
        abort(400, description="Зөвхөн type='page' цэсэнд контент хуудас үүсгэнэ")
    page = Page(menu_id=menu.id, title=data.get("title") or menu.title,
                body=data.get("body"), cover_image=data.get("cover_image"),
                status=data.get("status") or "draft", updated_at=_now())
    s.add(page)
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        abort(409, description="Энэ цэсэнд контент хуудас аль хэдийн үүссэн байна")
    return jsonify(page.to_dict()), 201


@bp.route("/api/page/<int:pid>", methods=["PUT", "PATCH"])
def update_page(pid):
    """Контент засах (title, body, cover_image, status) — pid нь ХУУДСАНЫ id."""
    data = json_body()
    _validate_page(data)
    values = pick(data, PAGE_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга. Сонголт: " + ", ".join(PAGE_FIELDS))
    s = session()
    page = s.get(Page, pid)
    if page is None:
        abort(404, description="Контент хуудас олдсонгүй")
    old_cover = page.cover_image
    for f, v in dict(values, updated_at=_now()).items():
        setattr(page, f, v)
    s.commit()
    # Cover солигдвол хуучин зургийг дискнээс арилгана.
    if "cover_image" in data and old_cover != data["cover_image"]:
        remove_upload(old_cover)
    return jsonify(page.to_dict())
