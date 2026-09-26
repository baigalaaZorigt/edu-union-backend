"""Хэрэглэгчийн inbox (§4) — /api/notifications (🔔): эрх шаардахгүй, зөвхөн өөрийн мөр."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import fail, rows, now_str

from admin.notifications import bp
from admin.notifications.common import INBOX_LIMIT, INBOX_MAX_LIMIT, dispatch_due, _user_id


# ============ Хэрэглэгчийн inbox (§4) — /api/notifications (🔔) ============
# Эрх шаардахгүй (auth.py-ийн SELF_PATHS / SELF_PREFIXES) — зөвхөн өөрийн мөрүүд.
@bp.route("/api/notifications", methods=["GET"])
def my_notifications():
    """Өөрийн inbox: {unread_count, items}. ?unread=1 бол зөвхөн уншаагүйг.

    ?limit= (анхдагч 50, дээд тал 200) — 🔔 цэс бүх түүхийг татахаас сэргийлнэ.
    """
    uid = _user_id()
    conn = get_db()
    dispatch_due(conn)                 # хуваарьт мэдэгдэл хугацаандаа inbox-д тусна
    unread_only = request.args.get("unread") in ("1", "true", "True")
    try:
        limit = min(INBOX_MAX_LIMIT, max(1, int(request.args.get("limit", INBOX_LIMIT))))
    except ValueError:
        fail(conn, 400, "limit нь тоо байх ёстой")
    cond = "r.user_id=?" + (" AND r.read_at IS NULL" if unread_only else "")
    data = rows(conn.execute(
        "SELECT n.id, n.title, n.body, n.type, n.image_url, n.sent_at, "
        "       r.read_at, r.created_at "
        "  FROM notification_recipients r "
        "  JOIN notifications n ON n.id = r.notification_id "
        f" WHERE {cond} ORDER BY r.id DESC LIMIT ?", (uid, limit)).fetchall())
    unread = conn.execute(
        "SELECT COUNT(*) FROM notification_recipients WHERE user_id=? AND read_at IS NULL",
        (uid,)).fetchone()[0]
    conn.close()
    return jsonify(unread_count=unread, items=data)


@bp.route("/api/notifications/<int:nid>/read", methods=["POST"])
def mark_read(nid):
    """Өөрийн inbox-ийн мөрийг уншсан болгоно (эхний уншсан цаг хадгалагдана)."""
    uid = _user_id()
    conn = get_db()
    cur = conn.execute(
        "UPDATE notification_recipients SET read_at=COALESCE(read_at, ?) "
        "WHERE notification_id=? AND user_id=?", (now_str(), nid, uid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Танд ирсэн ийм мэдэгдэл олдсонгүй")
    return jsonify(status=True)
