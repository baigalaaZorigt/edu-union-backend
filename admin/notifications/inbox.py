"""Хэрэглэгчийн inbox (§4) — /api/notifications (🔔): эрх шаардахгүй, зөвхөн өөрийн мөр."""

from flask import jsonify, request, abort
from sqlalchemy import func, select, update

from core.helpers import now_str
from core.orm import session
from core.orm.models import Notification, NotificationRecipient as Rcpt

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
    s = session()
    dispatch_due(s)                    # хуваарьт мэдэгдэл хугацаандаа inbox-д тусна
    unread_only = request.args.get("unread") in ("1", "true", "True")
    try:
        limit = min(INBOX_MAX_LIMIT, max(1, int(request.args.get("limit", INBOX_LIMIT))))
    except ValueError:
        abort(400, description="limit нь тоо байх ёстой")
    conds = [Rcpt.user_id == uid] + ([Rcpt.read_at.is_(None)] if unread_only else [])
    data = s.execute(
        select(Notification.id, Notification.title, Notification.body, Notification.type,
               Notification.image_url, Notification.sent_at, Rcpt.read_at, Rcpt.created_at)
        .join(Notification, Notification.id == Rcpt.notification_id)
        .where(*conds).order_by(Rcpt.id.desc()).limit(limit)).mappings().all()
    unread = s.scalar(select(func.count()).select_from(Rcpt)
                      .where(Rcpt.user_id == uid, Rcpt.read_at.is_(None)))
    return jsonify(unread_count=unread, items=[dict(r) for r in data])


@bp.route("/api/notifications/<int:nid>/read", methods=["POST"])
def mark_read(nid):
    """Өөрийн inbox-ийн мөрийг уншсан болгоно (эхний уншсан цаг хадгалагдана)."""
    uid = _user_id()
    s = session()
    res = s.execute(update(Rcpt).where(Rcpt.notification_id == nid, Rcpt.user_id == uid)
                    .values(read_at=func.coalesce(Rcpt.read_at, now_str()))
                    .execution_options(synchronize_session=False))
    s.commit()
    if res.rowcount == 0:
        abort(404, description="Танд ирсэн ийм мэдэгдэл олдсонгүй")
    return jsonify(status=True)
