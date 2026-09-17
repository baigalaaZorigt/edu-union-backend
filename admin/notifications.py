"""Мэдэгдэл — админы илгээх тал + хэрэглэгчийн өөрийн inbox (Blueprint).

notification_api_spec.md-ийн хоёр хэсгийг НЭГ модуль хангана (frontend-ийн 2 дэлгэц):
    /api/admin/notifications        — админ бичиж илгээх, жагсаалт, устгах (§3)
    /api/notifications              — толгойн 🔔 дуут дохио: өөрийн inbox (§4)

Бүтэц: `notifications` (нэг мэдэгдэл) -> `notification_recipients` (fan-out:
хамрах хэрэглэгч бүрт нэг мөр + `read_at`). Хоёр site-д хуваагдахгүй (хоёулаа
admin site-ийн хэрэглэгчид) тул тусад нь `*_core` модуль гаргаагүй.

Inbox нь эрхээс ХАМААРАХГҮЙ: `/api/notifications` нь auth.py-ийн SELF_PATHS /
SELF_PREFIXES дотор — токен шаардана ч `notification.read` эрх шаардахгүй,
учир нь зөвхөн g.user-ийн ӨӨРИЙН мөрүүдэд хүрдэг (admin тал нь эрхтэй хэвээр).

Хуваарьт (scheduled) мэдэгдэл: `dispatch_due()` нь `scheduled_at` хүрсэн
мэдэгдлүүдийг илгээнэ. Репод үйлчилгээний scheduler байхгүй тул үүнийг
  * `send_due_notifications.py` (cron/systemd timer дуудна), мөн
  * жагсаалт/inbox уншихад ЗАЛХУУ (lazy) — cron тохируулаагүй ч ажиллахын тулд
хоёр талаас дуудна. Fan-out нь INSERT OR IGNORE + UNIQUE тул хэд ч удаа
ажиллуулахад аюулгүй.
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, abort, g

from db import get_db
from helpers import rows

bp = Blueprint("notifications", __name__)

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
def now_str():
    """Одоогийн UTC цаг — "YYYY-MM-DD HH:MM:SS" (forms/news/feedback-тэй ижил).

    Текстээр харьцуулахад ч дараалал зөв хэвээр байдаг тул `scheduled_at <= now`
    гэсэн шалгалт SQL дотор ажиллана.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def bad(conn, message, code=400):
    """Холболтыг хааж байгаад алдаа шидэнэ (холболт алдагдахаас сэргийлнэ)."""
    if conn is not None:
        conn.close()
    abort(code, description=message)


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
        bad(conn, "scheduled_at нь текст огноо байх ёстой")
    raw = value.strip().replace("T", " ")
    if raw.endswith("Z"):
        raw = raw[:-1]
    raw = raw.split("+")[0].split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    bad(conn, "scheduled_at буруу (ж: 2026-09-20 09:00:00)")


def _ids(conn, value):
    """user_ids-ийг бүхэл тооны жагсаалт болгоно (эс бөгөөс 400)."""
    if not isinstance(value, list):
        bad(conn, "user_ids нь массив байх ёстой")
    try:
        return [int(x) for x in value]
    except (TypeError, ValueError):
        bad(conn, "user_ids нь бүхэл тооны массив байх ёстой")


def _validate(conn, data):
    """Мэдэгдлийн их биеийг шалгаад, хадгалахад бэлэн dict буцаана (зөрвөл 400)."""
    if not isinstance(data, dict):
        bad(conn, "JSON их бие шаардлагатай")

    out = {}
    for f in ("title", "body"):
        val = data.get(f)
        out[f] = val.strip() if isinstance(val, str) else None
        if not out[f]:
            bad(conn, f"Дутуу талбар: {f}")
    for f, limit in MAX_LEN.items():
        if len(out[f]) > limit:
            bad(conn, f"{f} нь {limit} тэмдэгтээс урт байж болохгүй")

    out["type"] = data.get("type") or "info"
    if out["type"] not in TYPES:
        bad(conn, "type буруу. Сонголт: " + ", ".join(TYPES))

    image = data.get("image_url")
    out["image_url"] = image.strip() if isinstance(image, str) and image.strip() else None

    audience = data.get("audience_type")
    if audience not in AUDIENCE_TYPES:
        bad(conn, "audience_type буруу. Сонголт: " + ", ".join(AUDIENCE_TYPES))
    out["audience_type"] = audience

    # Хаяглалтын хэлбэр — user_scope-той ижил зарчмаар ХАТУУ шалгана: төрөл
    # бүрт зөвхөн өөрт хамаарах талбар нь ирнэ.
    role_id = data.get("role_id")
    picked = data.get("user_ids")
    if audience == "role":
        if role_id is None:
            bad(conn, "audience_type='role' үед role_id заавал")
        if not conn.execute("SELECT 1 FROM role WHERE id=?", (role_id,)).fetchone():
            bad(conn, "role_id (дүр) олдсонгүй")
        if picked:
            bad(conn, "audience_type='role' үед user_ids хоосон байх ёстой")
        out["role_id"], out["audience_user_ids"] = role_id, None
    elif audience == "picked":
        ids = _ids(conn, picked if picked is not None else [])
        if not ids:
            bad(conn, "audience_type='picked' үед user_ids заавал (хоосон биш)")
        if role_id is not None:
            bad(conn, "audience_type='picked' үед role_id сонгохгүй")
        for uid in ids:
            if not conn.execute("SELECT 1 FROM app_user WHERE id=?", (uid,)).fetchone():
                bad(conn, f"user_ids: {uid} дугаартай хэрэглэгч олдсонгүй")
        out["role_id"] = None
        out["audience_user_ids"] = json.dumps(sorted(set(ids)))
    else:                                     # all
        if role_id is not None or picked:
            bad(conn, "audience_type='all' үед role_id / user_ids сонгохгүй")
        out["role_id"], out["audience_user_ids"] = None, None

    out["scheduled_at"] = _parse_when(conn, data.get("scheduled_at"))
    return out


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
    try:
        ids = json.loads(row["audience_user_ids"] or "[]")
    except ValueError:
        ids = []
    return [int(x) for x in ids] if isinstance(ids, list) else []


def _fan_out(conn, nid, user_ids):
    """Хүлээн авагч бүрт inbox мөр үүсгэнэ (давхардвал алгасна)."""
    now = now_str()
    conn.executemany(
        "INSERT OR IGNORE INTO notification_recipients"
        "(notification_id, user_id, created_at, updated_at) VALUES (?,?,?,?)",
        [(nid, uid, now, now) for uid in user_ids])
    return len(user_ids)


def _send(conn, nid, row):
    """Мэдэгдлийг ИЛГЭЭНЭ: fan-out, дараа нь status='sent'.

    Эхлээд fan-out (idempotent), дараа нь төлөвийг нөхцөлтэйгөөр сольдог —
    ингэснээр яг тэр мөчид процесс унасан ч дараагийн dispatch нөхнө.
    """
    count = _fan_out(conn, nid, _audience_ids(conn, row))
    conn.execute("UPDATE notifications SET status='sent', sent_at=? WHERE id=?",
                 (now_str(), nid))
    return count


def dispatch_due(conn):
    """`scheduled_at` хүрсэн хуваарьт мэдэгдлүүдийг илгээнэ; илгээсэн тоог буцаана.

    Хэд ч удаа, зэрэг ажиллуулахад аюулгүй: recipients нь UNIQUE-аар хамгаалагдсан,
    төлөв солих нь `status='scheduled'` нөхцөлтэй (хоёр дахь нь 0 мөр шинэчилнэ).
    """
    now = now_str()
    due = conn.execute(
        "SELECT * FROM notifications WHERE status='scheduled' "
        "AND scheduled_at IS NOT NULL AND scheduled_at <= ? ORDER BY id", (now,)).fetchall()
    sent = 0
    for row in due:
        _fan_out(conn, row["id"], _audience_ids(conn, row))
        cur = conn.execute(
            "UPDATE notifications SET status='sent', sent_at=? "
            "WHERE id=? AND status='scheduled'", (now, row["id"]))
        sent += cur.rowcount or 0
    if due:
        conn.commit()
    return sent


def _public(row):
    """Админы жагсаалтын хэлбэр (спек §3) — тоологдсон талбаруудтай хамт."""
    out = {f: row[f] for f in
           ("id", "title", "body", "type", "image_url", "audience_type", "role_id",
            "status", "scheduled_at", "sent_at", "created_by", "created_at")}
    out["role_name"] = row["role_name"]
    out["recipient_count"] = row["recipient_count"]
    out["read_count"] = row["read_count"]
    try:
        ids = json.loads(row["audience_user_ids"] or "[]")
    except ValueError:
        ids = []
    out["user_ids"] = ids if isinstance(ids, list) else []
    return out


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
        bad(conn, "page / per_page нь тоо байх ёстой")
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
        bad(conn, "Мэдэгдэл олдсонгүй", 404)
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
        bad(conn, "status буруу. Сонголт: " + ", ".join(STATUSES))
    if wanted == "draft":
        status = "draft"
    elif values["scheduled_at"]:
        status = "scheduled"
    else:
        status = "sent"

    now = now_str()
    cols = list(NOTIFY_FIELDS) + ["status", "created_by", "created_at", "updated_at"]
    params = [values[f] for f in NOTIFY_FIELDS] + [status, _user_id(), now, now]
    cur = conn.execute(
        f"INSERT INTO notifications({', '.join(cols)}) "
        f"VALUES ({', '.join('?' * len(cols))})", params)
    nid = cur.lastrowid
    if status == "sent":
        _send(conn, nid, conn.execute(
            "SELECT * FROM notifications WHERE id=?", (nid,)).fetchone())
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
        bad(conn, "Мэдэгдэл олдсонгүй", 404)
    hard = request.args.get("hard") in ("1", "true", "True")
    if row["status"] == "sent" and not hard:
        bad(conn, "Илгээгдсэн мэдэгдлийг буцаах боломжгүй "
                  "(шаардвал ?hard=1-ээр бүрмөсөн устгана)", 422)
    conn.execute("DELETE FROM notifications WHERE id=?", (nid,))   # recipients cascade
    conn.commit()
    conn.close()
    return jsonify(deleted=nid)


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
        bad(conn, "limit нь тоо байх ёстой")
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
