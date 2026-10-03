"""Мэдэгдлийн хуваалцсан хэсэг: тогтмол, шалгалт, fan-out, dispatch_due."""

import json
from datetime import datetime

from flask import abort, g
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core.helpers import now_str
from core.orm import session
from core.orm.models import AppUser, Notification, NotificationRecipient, Role


MAX_PER_PAGE = 100
INBOX_LIMIT = 50                       # 🔔 дуут дохионы анхдагч тоо
INBOX_MAX_LIMIT = 200

TYPES = ("info", "reminder", "urgent")
AUDIENCE_TYPES = ("all", "role", "picked")
STATUSES = ("draft", "scheduled", "sent")

MAX_LEN = {"title": 300}

# Оруулж болох талбарууд (status/sent_at/created_by нь СЕРВЕР талд тодорхойлогдоно)
NOTIFY_FIELDS = ("title", "body", "type", "image_url", "audience_type", "role_id",
                 "audience_user_ids", "scheduled_at")

# Админы жагсаалтын хариунд гарах мөрийн талбарууд (спек §3)
PUBLIC_FIELDS = ("id", "title", "body", "type", "image_url", "audience_type", "role_id",
                 "status", "scheduled_at", "sent_at", "created_by", "created_at",
                 "role_name", "recipient_count", "read_count")

# Жагсаалтад хүлээн авагчийн тоо ба уншсаны тоог хамт (денормалчилсан талбарууд)
def notify_query():
    """select(Notification, role_name, recipient_count, read_count) — шүүлтийг дуудагч нэмнэ."""
    rcpt = NotificationRecipient
    recipient_count = (select(func.count()).select_from(rcpt)
                       .where(rcpt.notification_id == Notification.id)
                       .correlate(Notification).scalar_subquery())
    read_count = (select(func.count()).select_from(rcpt)
                  .where(rcpt.notification_id == Notification.id, rcpt.read_at.is_not(None))
                  .correlate(Notification).scalar_subquery())
    return (select(Notification, Role.name.label("role_name"),
                   recipient_count.label("recipient_count"), read_count.label("read_count"))
            .outerjoin(Role, Role.id == Notification.role_id))


# ----------------------------- Туслахууд -----------------------------
def _user_id():
    """Токен эзэмшигчийн id (before_request нь g.user-ыг ачаалсан байх ёстой)."""
    user = getattr(g, "user", None)
    if user is None:
        abort(401, description="Нэвтрэх шаардлагатай")
    return user["id"]


def _fail(code, message):
    abort(code, description=message)


def _parse_when(value):
    """Хуваарийн цагийг "YYYY-MM-DD HH:MM:SS" болгоно (ISO-г ч хүлээж авна)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        _fail(400, "scheduled_at нь текст огноо байх ёстой")
    raw = value.strip().replace("T", " ")
    if raw.endswith("Z"):
        raw = raw[:-1]
    raw = raw.split("+")[0].split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    _fail(400, "scheduled_at буруу (ж: 2026-09-20 09:00:00)")


def _ids(value):
    """user_ids-ийг бүхэл тооны жагсаалт болгоно (эс бөгөөс 400)."""
    if not isinstance(value, list):
        _fail(400, "user_ids нь массив байх ёстой")
    try:
        return [int(x) for x in value]
    except (TypeError, ValueError):
        _fail(400, "user_ids нь бүхэл тооны массив байх ёстой")


def _validate(data):
    """Мэдэгдлийн их биеийг шалгаад, хадгалахад бэлэн dict буцаана (зөрвөл 400)."""
    if not isinstance(data, dict):
        _fail(400, "JSON их бие шаардлагатай")

    out = {}
    for f in ("title", "body"):
        val = data.get(f)
        out[f] = val.strip() if isinstance(val, str) else None
        if not out[f]:
            _fail(400, f"Дутуу талбар: {f}")
    for f, limit in MAX_LEN.items():
        if len(out[f]) > limit:
            _fail(400, f"{f} нь {limit} тэмдэгтээс урт байж болохгүй")

    out["type"] = data.get("type") or "info"
    if out["type"] not in TYPES:
        _fail(400, "type буруу. Сонголт: " + ", ".join(TYPES))

    image = data.get("image_url")
    out["image_url"] = image.strip() if isinstance(image, str) and image.strip() else None

    audience = data.get("audience_type")
    if audience not in AUDIENCE_TYPES:
        _fail(400, "audience_type буруу. Сонголт: " + ", ".join(AUDIENCE_TYPES))
    out["audience_type"] = audience

    # Хаяглалтын хэлбэр — user_scope-той ижил зарчмаар ХАТУУ шалгана: төрөл
    # бүрт зөвхөн өөрт хамаарах талбар нь ирнэ.
    role_id = data.get("role_id")
    picked = data.get("user_ids")
    if audience == "role":
        if role_id is None:
            _fail(400, "audience_type='role' үед role_id заавал")
        if session().scalar(select(Role.id).where(Role.id == role_id)) is None:
            _fail(400, "role_id (дүр) олдсонгүй")
        if picked:
            _fail(400, "audience_type='role' үед user_ids хоосон байх ёстой")
        out["role_id"], out["audience_user_ids"] = role_id, None
    elif audience == "picked":
        ids = _ids(picked if picked is not None else [])
        if not ids:
            _fail(400, "audience_type='picked' үед user_ids заавал (хоосон биш)")
        if role_id is not None:
            _fail(400, "audience_type='picked' үед role_id сонгохгүй")
        for uid in ids:
            if session().scalar(select(AppUser.id).where(AppUser.id == uid)) is None:
                _fail(400, f"user_ids: {uid} дугаартай хэрэглэгч олдсонгүй")
        out["role_id"] = None
        out["audience_user_ids"] = json.dumps(sorted(set(ids)))
    else:                                     # all
        if role_id is not None or picked:
            _fail(400, "audience_type='all' үед role_id / user_ids сонгохгүй")
        out["role_id"], out["audience_user_ids"] = None, None

    out["scheduled_at"] = _parse_when(data.get("scheduled_at"))
    return out


def _stored_ids(raw):
    """`audience_user_ids` JSON текстийг жагсаалт болгоно (эвдэрсэн бол хоосон)."""
    try:
        ids = json.loads(raw or "[]")
    except ValueError:
        return []
    return ids if isinstance(ids, list) else []


def _audience_ids(s, n):
    """Мэдэгдлийн хаяглалтаас хүлээн авагчдын id-уудыг гаргана.

    all / role — ЗӨВХӨН идэвхтэй хэрэглэгчид (идэвхгүй болсон хүн нэвтэрч
    уншиж чадахгүй). picked — админ тодорхой сонгосон тул хэвээр нь.
    """
    if n.audience_type == "all":
        return list(s.scalars(select(AppUser.id).where(AppUser.is_active == 1)
                              .order_by(AppUser.id)))
    if n.audience_type == "role":
        return list(s.scalars(select(AppUser.id).where(AppUser.is_active == 1,
                                                       AppUser.role_id == n.role_id)
                              .order_by(AppUser.id)))
    return [int(x) for x in _stored_ids(n.audience_user_ids)]


def _fan_out(s, nid, user_ids):
    """Хүлээн авагч бүрт inbox мөр үүсгэнэ (давхардвал алгасна — UNIQUE дээр
    ON CONFLICT DO NOTHING; зэрэг ажилласан dispatch ч алдаа өгөхгүй)."""
    if user_ids:
        now = now_str()
        sender = s.scalar(select(Notification.created_by).where(Notification.id == nid))
        insert = pg_insert if s.get_bind().dialect.name == "postgresql" else sqlite_insert
        s.execute(insert(NotificationRecipient)
                  .values([{"notification_id": nid, "user_id": uid, "created_at": now,
                            "updated_at": now, "created_by": sender} for uid in user_ids])
                  .on_conflict_do_nothing(index_elements=["notification_id", "user_id"]))
    return len(user_ids)


def _send(s, n, now):
    """Мэдэгдлийг ИЛГЭЭНЭ: fan-out, дараа нь status='sent' + sent_at.

    Эхлээд fan-out (idempotent), дараа нь төлөвийг мөрийн ОДООГИЙН төлөвийн
    нөхцөлтэйгөөр сольдог — зэрэг ажилласан хоёр dispatch-ийн хоёр дахь нь 0 мөр
    шинэчилнэ, яг тэр мөчид процесс унасан ч дараагийн dispatch нөхнө.
    Шинэчилсэн мөрийн тоог (0/1) буцаана.
    """
    nid, status = n.id, n.status
    _fan_out(s, nid, _audience_ids(s, n))
    res = s.execute(update(Notification)
                    .where(Notification.id == nid, Notification.status == status)
                    .values(status="sent", sent_at=now)
                    .execution_options(synchronize_session=False))
    s.expire(n)
    return res.rowcount or 0


def dispatch_due(s=None):
    """`scheduled_at` хүрсэн хуваарьт мэдэгдлүүдийг илгээнэ; илгээсэн тоог буцаана.

    Хэд ч удаа, зэрэг ажиллуулахад аюулгүй: recipients нь UNIQUE-аар хамгаалагдсан,
    төлөв солих нь `status='scheduled'` нөхцөлтэй (хоёр дахь нь 0 мөр шинэчилнэ).
    s — session (скрипт өөрийнхөө new_session()-ийг өгнө); өгөөгүй бол хүсэлтийнх.
    """
    s = s or session()
    now = now_str()
    due = s.scalars(select(Notification)
                    .where(Notification.status == "scheduled",
                           Notification.scheduled_at.is_not(None),
                           Notification.scheduled_at <= now)
                    .order_by(Notification.id)).all()
    sent = sum(_send(s, n, now) for n in due)
    if due:
        s.commit()
    return sent


def _public(row):
    """Админы жагсаалтын хэлбэр (спек §3) — notify_query()-ийн мөр (тоологдсон талбартай)."""
    n = row[0]
    extra = {"role_name": row.role_name, "recipient_count": row.recipient_count,
             "read_count": row.read_count}
    out = {f: extra[f] if f in extra else getattr(n, f) for f in PUBLIC_FIELDS}
    out["user_ids"] = _stored_ids(n.audience_user_ids)
    return out
