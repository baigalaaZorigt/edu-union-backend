"""Админ тал (§3) — /api/admin/notifications: бичих, илгээх, жагсаалт, устгах."""

from flask import abort, jsonify, request
from sqlalchemy import delete, func, select

from core.helpers import now_str
from core.orm import session
from core.orm.models import Notification

from admin.notifications import bp
from admin.notifications.common import (MAX_PER_PAGE, NOTIFY_FIELDS, STATUSES, dispatch_due,
                                        notify_query, _public, _send, _user_id, _validate)


def _one(nid):
    return session().execute(notify_query().where(Notification.id == nid)).first()


# ================= Админ тал (§3) — /api/admin/notifications =================
@bp.route("/api/admin/notifications", methods=["GET"])
def list_notifications():
    """Мэдэгдлийн жагсаалт. Шүүлт: ?status= &type= &search= &page= &per_page="""
    s = session()
    dispatch_due(s)                    # хуваарьт нь хугацаа хүрсэн бол эхлээд илгээнэ
    conds = [getattr(Notification, f) == request.args[f] for f in ("status", "type")
             if request.args.get(f)]
    search = (request.args.get("search") or "").strip()
    if search:
        pat = f"%{search}%"
        conds.append(Notification.title.ilike(pat) | Notification.body.ilike(pat))
    total = s.scalar(select(func.count()).select_from(Notification).where(*conds))
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        abort(400, description="page / per_page нь тоо байх ёстой")
    data = s.execute(notify_query().where(*conds).order_by(Notification.id.desc())
                     .limit(per_page).offset((page - 1) * per_page)).all()
    return jsonify(items=[_public(r) for r in data], total=total, page=page,
                   per_page=per_page, pages=(total + per_page - 1) // per_page)


@bp.route("/api/admin/notifications/<int:nid>", methods=["GET"])
def get_notification(nid):
    """Нэг мэдэгдэл (хүлээн авагчдын тоо, уншсаны тоотой)."""
    row = _one(nid)
    if row is None:
        abort(404, description="Мэдэгдэл олдсонгүй")
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
    values = _validate(data)
    wanted = data.get("status")
    if wanted is not None and wanted not in STATUSES:
        abort(400, description="status буруу. Сонголт: " + ", ".join(STATUSES))
    if wanted == "draft":
        status = "draft"
    elif values["scheduled_at"]:
        status = "scheduled"
    else:
        status = "sent"
    now = now_str()
    s = session()
    n = Notification(**{f: values[f] for f in NOTIFY_FIELDS}, status=status,
                     created_by=_user_id(), created_at=now, updated_at=now)
    s.add(n)
    s.flush()
    if status == "sent":
        _send(s, n, now)
    s.commit()
    return jsonify(_public(_one(n.id))), 201


@bp.route("/api/admin/notifications/<int:nid>", methods=["DELETE"])
def delete_notification(nid):
    """Устгах/цуцлах — ЗӨВХӨН draft / scheduled (илгээгдсэнийг буцаах боломжгүй → 422).

    `?hard=1` нь илгээгдсэнийг ч хүчээр устгана (хүлээн авагчдын мөр cascade-аар
    арилна) — `DELETE /api/admin/forms/<id>?hard=1`-тэй ижил гаргалгаа. Хүн
    санамсаргүй дарахаас хамгаалахын тулд зориуд ТОДОРХОЙ параметртэй.
    """
    s = session()
    status = s.scalar(select(Notification.status).where(Notification.id == nid))
    if status is None:
        abort(404, description="Мэдэгдэл олдсонгүй")
    hard = request.args.get("hard") in ("1", "true", "True")
    if status == "sent" and not hard:
        abort(422, description="Илгээгдсэн мэдэгдлийг буцаах боломжгүй "
                               "(шаардвал ?hard=1-ээр бүрмөсөн устгана)")
    s.execute(delete(Notification).where(Notification.id == nid))   # recipients cascade
    s.commit()
    return jsonify(deleted=nid)
