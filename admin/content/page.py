"""page (Контент хуудас) — type='page' цэс бүрд нэг бичлэг."""

from flask import jsonify, request

from core.db import get_db
from core.helpers import rows, require, json_body, fail, pick, insert_row, update_row

from admin.content import bp
from admin.content.storage import remove_upload
from admin.content.common import _blocks_of, _now


# Хуудасны засаж болох талбарууд
PAGE_FIELDS = ("title", "body", "cover_image", "status")
PAGE_STATUSES = ("published", "draft")


# ======================= page (Контент хуудас) =======================
@bp.route("/api/page/<int:menu_id>", methods=["GET"])
def get_page(menu_id):
    """Тухайн ЦЭСНИЙ контентыг блок/зураг/файл/видеотой нь буцаана.

    Анхаар: спекийн дагуу GET нь menu_id-аар, PUT нь page id-аар ажиллана.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM page WHERE menu_id=?", (menu_id,)).fetchone()
    if not row:
        fail(conn, 404, "Энэ цэсэнд контент хуудас алга")
    data = dict(row, blocks=_blocks_of(conn, row["id"]))
    for key, btype in (("images", "image"), ("files", "file"), ("videos", "video")):
        data[key] = _blocks_of(conn, row["id"], btype)
    conn.close()
    return jsonify(data)


@bp.route("/api/page", methods=["GET"])
def list_page():
    """Бүх контент хуудас (цэсний нэртэй нь). Админ жагсаалтад зориулав."""
    conn = get_db()
    data = rows(conn.execute(
        "SELECT p.*, m.title AS menu_title, m.slug AS menu_slug "
        "FROM page p JOIN menu m ON m.id = p.menu_id "
        "ORDER BY p.id").fetchall())
    conn.close()
    return jsonify(data)


def _validate_page(conn, data):
    status = data.get("status")
    if status and status not in PAGE_STATUSES:
        fail(conn, 400, "status буруу. Сонголт: " + ", ".join(PAGE_STATUSES))


@bp.route("/api/page", methods=["POST"])
def create_page():
    """Цэсэнд контент хуудас үүсгэх (type='page' цэсэнд нэг л удаа)."""
    data = request.get_json(silent=True)
    require(data, ["menu_id"])
    conn = get_db()
    _validate_page(conn, data)
    menu = conn.execute("SELECT * FROM menu WHERE id=?", (data["menu_id"],)).fetchone()
    if not menu:
        fail(conn, 400, "menu_id (цэс) олдсонгүй")
    if menu["type"] != "page":
        fail(conn, 400, "Зөвхөн type='page' цэсэнд контент хуудас үүсгэнэ")
    try:
        pid = insert_row(conn, "page", {
            "menu_id": menu["id"], "title": data.get("title") or menu["title"],
            "body": data.get("body"), "cover_image": data.get("cover_image"),
            "status": data.get("status") or "draft", "updated_at": _now()})
    except Exception:
        fail(conn, 409, "Энэ цэсэнд контент хуудас аль хэдийн үүссэн байна")
    conn.commit()
    row = conn.execute("SELECT * FROM page WHERE id=?", (pid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/page/<int:pid>", methods=["PUT", "PATCH"])
def update_page(pid):
    """Контент засах (title, body, cover_image, status) — pid нь ХУУДСАНЫ id."""
    data = json_body()
    conn = get_db()
    _validate_page(conn, data)
    values = pick(data, PAGE_FIELDS)
    if not values:
        fail(conn, 400, "Шинэчлэх талбар алга. Сонголт: " + ", ".join(PAGE_FIELDS))
    old = conn.execute("SELECT cover_image FROM page WHERE id=?", (pid,)).fetchone()
    if not update_row(conn, "page", pid, dict(values, updated_at=_now())):
        fail(conn, 404, "Контент хуудас олдсонгүй")
    conn.commit()
    row = conn.execute("SELECT * FROM page WHERE id=?", (pid,)).fetchone()
    conn.close()
    # Cover солигдвол хуучин зургийг дискнээс арилгана.
    if "cover_image" in data and old and old["cover_image"] != data["cover_image"]:
        remove_upload(old["cover_image"])
    return jsonify(dict(row))
