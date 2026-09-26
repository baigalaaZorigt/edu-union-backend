"""Админ тал (§3) — /api/admin/notifications: бичих, илгээх, жагсаалт, устгах."""

from flask import jsonify, request

from core.db import get_db
from core.helpers import fail, insert_row, now_str

from admin.notifications import bp
from admin.notifications.common import (MAX_PER_PAGE, NOTIFY_FIELDS, NOTIFY_SELECT, STATUSES,
                                        dispatch_due, _public, _send, _user_id, _validate)


# ================= Админ тал (§3) — /api/admin/notifications =================
@bp.route("/api/admin/notifications", methods=["GET"])
def list_notifications():
    """Мэдэгдлийн жагсаалт. Шүүлт: ?status= &type= &search= &page= &per_page="""
    conn = get_db()
    dispatch_due(conn)                 # хуваарьт нь хугацаа хүрсэн бол эхлээд илгээнэ
    where, args = [], []
    for f in ("status", "type"):
        if request.args.get(f):
            where.append(f"n.{f}=?")
            args.append(request.args[f])
    search = (request.args.get("search") or "").strip()
    if search:
        where.append("(n.title LIKE ? OR n.body LIKE ?)")
        args += [f"%{search}%", f"%{search}%"]
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute("SELECT COUNT(*) FROM notifications n" + clause, args).fetchone()[0]
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        fail(conn, 400, "page / per_page нь тоо байх ёстой")
    data = conn.execute(
        NOTIFY_SELECT + clause + " ORDER BY n.id DESC LIMIT ? OFFSET ?",
        args + [per_page, (page - 1) * per_page]).fetchall()
    conn.close()
    return jsonify(items=[_public(r) for r in data], total=total, page=page,
                   per_page=per_page, pages=(total + per_page - 1) // per_page)


@bp.route("/api/admin/notifications/<int:nid>", methods=["GET"])
def get_notification(nid):
    """Нэг мэдэгдэл (хүлээн авагчдын тоо, уншсаны тоотой)."""
    conn = get_db()
    row = conn.execute(NOTIFY_SELECT + " WHERE n.id=?", (nid,)).fetchone()
    if not row:
        fail(conn, 404, "Мэдэгдэл олдсонгүй")
    conn.close()
    return jsonify(_public(row))


@bp.route("/api/admin/notifications", methods=["POST"])
def create_notification():
    """Мэдэгдэл үүсгэж илгээнэ (спек §3).

    - `scheduled_at` өгөөгүй бол ШУУД `status='sent'` + fan-out
    - `scheduled_at` өгвөл `status='scheduled'` (хугацаа хүрэхэд dispatch илгээнэ)
    - `status='draft'` гэж тодорхой өгвөл хадгалаад илгээхгүй (спекийн DELETE нь
      draft-ыг дурддаг тул үүсгэх арга байх ёстой)
    """
    data = request.get_json(silent=True)
    conn = get_db()
    values = _validate(conn, data)
    wanted = data.get("status")
    if wanted is not None and wanted not in STATUSES:
        fail(conn, 400, "status буруу. Сонголт: " + ", ".join(STATUSES))
    if wanted == "draft":
        status = "draft"
    elif values["scheduled_at"]:
        status = "scheduled"
    else:
        status = "sent"

    now = now_str()
    nid = insert_row(conn, "notifications", {
        **{f: values[f] for f in NOTIFY_FIELDS},
        "status": status, "created_by": _user_id(), "created_at": now, "updated_at": now})
    if status == "sent":
        _send(conn, conn.execute(
            "SELECT * FROM notifications WHERE id=?", (nid,)).fetchone(), now)
    conn.commit()
    row = conn.execute(NOTIFY_SELECT + " WHERE n.id=?", (nid,)).fetchone()
    conn.close()
    return jsonify(_public(row)), 201


@bp.route("/api/admin/notifications/<int:nid>", methods=["DELETE"])
def delete_notification(nid):
    """Устгах/цуцлах — ЗӨВХӨН draft / scheduled (илгээгдсэнийг буцаах боломжгүй → 422).

    `?hard=1` нь илгээгдсэнийг ч хүчээр устгана (хүлээн авагчдын мөр cascade-аар
    арилна) — `DELETE /api/admin/forms/<id>?hard=1`-тэй ижил гаргалгаа. Хүн
    санамсаргүй дарахаас хамгаалахын тулд зориуд ТОДОРХОЙ параметртэй.
    """
    conn = get_db()
    row = conn.execute("SELECT status FROM notifications WHERE id=?", (nid,)).fetchone()
    if not row:
        fail(conn, 404, "Мэдэгдэл олдсонгүй")
    hard = request.args.get("hard") in ("1", "true", "True")
    if row["status"] == "sent" and not hard:
        fail(conn, 422, "Илгээгдсэн мэдэгдлийг буцаах боломжгүй "
                        "(шаардвал ?hard=1-ээр бүрмөсөн устгана)")
    conn.execute("DELETE FROM notifications WHERE id=?", (nid,))   # recipients cascade
    conn.commit()
    conn.close()
    return jsonify(deleted=nid)
