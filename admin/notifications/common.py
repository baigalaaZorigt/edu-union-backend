"""Мэдэгдлийн хуваалцсан хэсэг: тогтмол, шалгалт, fan-out, dispatch_due."""

import json
from datetime import datetime

from flask import abort, g

from core.helpers import fail, now_str


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
NOTIFY_SELECT = """
SELECT n.*, r.name AS role_name,
       (SELECT COUNT(*) FROM notification_recipients x WHERE x.notification_id = n.id)
         AS recipient_count,
       (SELECT COUNT(*) FROM notification_recipients x WHERE x.notification_id = n.id
          AND x.read_at IS NOT NULL) AS read_count
  FROM notifications n
  LEFT JOIN role r ON r.id = n.role_id
"""


# ----------------------------- Туслахууд -----------------------------
def _user_id():
    """Токен эзэмшигчийн id (before_request нь g.user-ыг ачаалсан байх ёстой)."""
    user = getattr(g, "user", None)
    if user is None:
        abort(401, description="Нэвтрэх шаардлагатай")
    return user["id"]


def _parse_when(conn, value):
    """Хуваарийн цагийг "YYYY-MM-DD HH:MM:SS" болгоно (ISO-г ч хүлээж авна)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        fail(conn, 400, "scheduled_at нь текст огноо байх ёстой")
    raw = value.strip().replace("T", " ")
    if raw.endswith("Z"):
        raw = raw[:-1]
    raw = raw.split("+")[0].split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    fail(conn, 400, "scheduled_at буруу (ж: 2026-09-20 09:00:00)")


def _ids(conn, value):
    """user_ids-ийг бүхэл тооны жагсаалт болгоно (эс бөгөөс 400)."""
    if not isinstance(value, list):
        fail(conn, 400, "user_ids нь массив байх ёстой")
    try:
        return [int(x) for x in value]
    except (TypeError, ValueError):
        fail(conn, 400, "user_ids нь бүхэл тооны массив байх ёстой")


def _validate(conn, data):
    """Мэдэгдлийн их биеийг шалгаад, хадгалахад бэлэн dict буцаана (зөрвөл 400)."""
    if not isinstance(data, dict):
        fail(conn, 400, "JSON их бие шаардлагатай")

    out = {}
    for f in ("title", "body"):
        val = data.get(f)
        out[f] = val.strip() if isinstance(val, str) else None
        if not out[f]:
            fail(conn, 400, f"Дутуу талбар: {f}")
    for f, limit in MAX_LEN.items():
        if len(out[f]) > limit:
            fail(conn, 400, f"{f} нь {limit} тэмдэгтээс урт байж болохгүй")

    out["type"] = data.get("type") or "info"
    if out["type"] not in TYPES:
        fail(conn, 400, "type буруу. Сонголт: " + ", ".join(TYPES))

    image = data.get("image_url")
    out["image_url"] = image.strip() if isinstance(image, str) and image.strip() else None

    audience = data.get("audience_type")
    if audience not in AUDIENCE_TYPES:
        fail(conn, 400, "audience_type буруу. Сонголт: " + ", ".join(AUDIENCE_TYPES))
    out["audience_type"] = audience

    # Хаяглалтын хэлбэр — user_scope-той ижил зарчмаар ХАТУУ шалгана: төрөл
    # бүрт зөвхөн өөрт хамаарах талбар нь ирнэ.
    role_id = data.get("role_id")
    picked = data.get("user_ids")
    if audience == "role":
        if role_id is None:
            fail(conn, 400, "audience_type='role' үед role_id заавал")
        if not conn.execute("SELECT 1 FROM role WHERE id=?", (role_id,)).fetchone():
            fail(conn, 400, "role_id (дүр) олдсонгүй")
        if picked:
            fail(conn, 400, "audience_type='role' үед user_ids хоосон байх ёстой")
        out["role_id"], out["audience_user_ids"] = role_id, None
    elif audience == "picked":
        ids = _ids(conn, picked if picked is not None else [])
        if not ids:
            fail(conn, 400, "audience_type='picked' үед user_ids заавал (хоосон биш)")
        if role_id is not None:
            fail(conn, 400, "audience_type='picked' үед role_id сонгохгүй")
        for uid in ids:
            if not conn.execute("SELECT 1 FROM app_user WHERE id=?", (uid,)).fetchone():
                fail(conn, 400, f"user_ids: {uid} дугаартай хэрэглэгч олдсонгүй")
        out["role_id"] = None
        out["audience_user_ids"] = json.dumps(sorted(set(ids)))
    else:                                     # all
        if role_id is not None or picked:
            fail(conn, 400, "audience_type='all' үед role_id / user_ids сонгохгүй")
        out["role_id"], out["audience_user_ids"] = None, None

    out["scheduled_at"] = _parse_when(conn, data.get("scheduled_at"))
    return out


def _stored_ids(raw):
    """`audience_user_ids` JSON текстийг жагсаалт болгоно (эвдэрсэн бол хоосон)."""
    try:
        ids = json.loads(raw or "[]")
    except ValueError:
        return []
    return ids if isinstance(ids, list) else []


def _audience_ids(conn, row):
    """Мэдэгдлийн хаяглалтаас хүлээн авагчдын id-уудыг гаргана.

    all / role — ЗӨВХӨН идэвхтэй хэрэглэгчид (идэвхгүй болсон хүн нэвтэрч
    уншиж чадахгүй). picked — админ тодорхой сонгосон тул хэвээр нь.
    """
    audience = row["audience_type"]
    if audience == "all":
        return [r[0] for r in conn.execute(
            "SELECT id FROM app_user WHERE is_active=1 ORDER BY id")]
    if audience == "role":
        return [r[0] for r in conn.execute(
            "SELECT id FROM app_user WHERE is_active=1 AND role_id=? ORDER BY id",
            (row["role_id"],))]
    return [int(x) for x in _stored_ids(row["audience_user_ids"])]


def _fan_out(conn, nid, user_ids):
    """Хүлээн авагч бүрт inbox мөр үүсгэнэ (давхардвал алгасна)."""
    now = now_str()
    conn.executemany(
        "INSERT OR IGNORE INTO notification_recipients"
        "(notification_id, user_id, created_at, updated_at) VALUES (?,?,?,?)",
        [(nid, uid, now, now) for uid in user_ids])
    return len(user_ids)


def _send(conn, row, now):
    """Мэдэгдлийг ИЛГЭЭНЭ: fan-out, дараа нь status='sent' + sent_at.

    Эхлээд fan-out (idempotent), дараа нь төлөвийг мөрийн ОДООГИЙН төлөвийн
    нөхцөлтэйгөөр сольдог — зэрэг ажилласан хоёр dispatch-ийн хоёр дахь нь 0 мөр
    шинэчилнэ, яг тэр мөчид процесс унасан ч дараагийн dispatch нөхнө.
    Шинэчилсэн мөрийн тоог (0/1) буцаана.
    """
    _fan_out(conn, row["id"], _audience_ids(conn, row))
    return conn.execute(
        "UPDATE notifications SET status='sent', sent_at=? WHERE id=? AND status=?",
        (now, row["id"], row["status"])).rowcount or 0


def dispatch_due(conn):
    """`scheduled_at` хүрсэн хуваарьт мэдэгдлүүдийг илгээнэ; илгээсэн тоог буцаана.

    Хэд ч удаа, зэрэг ажиллуулахад аюулгүй: recipients нь UNIQUE-аар хамгаалагдсан,
    төлөв солих нь `status='scheduled'` нөхцөлтэй (хоёр дахь нь 0 мөр шинэчилнэ).
    """
    now = now_str()
    due = conn.execute(
        "SELECT * FROM notifications WHERE status='scheduled' "
        "AND scheduled_at IS NOT NULL AND scheduled_at <= ? ORDER BY id", (now,)).fetchall()
    sent = sum(_send(conn, row, now) for row in due)
    if due:
        conn.commit()
    return sent


def _public(row):
    """Админы жагсаалтын хэлбэр (спек §3) — тоологдсон талбаруудтай хамт."""
    out = {f: row[f] for f in PUBLIC_FIELDS}
    out["user_ids"] = _stored_ids(row["audience_user_ids"])
    return out
