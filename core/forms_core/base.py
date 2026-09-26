"""Маягтын (form) тогтмолууд, жижиг туслахууд, form-ийн шалгалт ба хэлбэржүүлэлт."""
import json
from datetime import datetime

from flask import abort, g

from core.helpers import now_str

FORM_TYPES = ("survey", "poll")
FORM_STATUSES = ("draft", "published", "closed")

# V1-д дэмжих асуултын төрлүүд (спекийн 6-р хэсэг)
QUESTION_TYPES = ("single_choice", "multiple_choice", "scale", "open_text")
CHOICE_TYPES = ("single_choice", "multiple_choice")     # form_option-той төрлүүд

# Оруулж/засаж болох талбарууд
FORM_FIELDS = ("type", "title", "description", "start_at", "end_at",
               "show_results", "one_response")
QUESTION_FIELDS = ("question_type", "title", "description", "is_required",
                   "sort_order", "settings")

SCALE_MIN, SCALE_MAX = 1, 10               # scale асуултын зөвшөөрөгдөх хүрээ
SCALE_DEFAULT_MAX = 5                      # settings.max өгөөгүй үеийн дээд утга


# ----------------------------- Жижиг туслахууд -----------------------------
def bad(conn, message, code=400):
    """Холболтыг хааж байгаад алдаа шидэнэ (холболт алдагдахаас сэргийлнэ)."""
    if conn is not None:
        conn.close()
    abort(code, description=message)


def current_user_id():
    """Одоо нэвтэрсэн хэрэглэгчийн id, ЗОЧИН бол None.

    /api/portal/* нь нээлттэй (auth.py-ийн PUBLIC_PREFIXES) тул нэвтрээгүй хүн ч
    хандана — тэр үед g.user огт байхгүй. Токен ирсэн бол auth.py-ийн
    _optional_user() түүнийг аль хэдийн ачаалсан байна.
    """
    user = getattr(g, "user", None)
    return user["id"] if user else None


def _flag(value, default=1):
    """true/false, 1/0, "1"/"0" -> 0/1."""
    if value is None:
        return default
    if isinstance(value, str):
        return 1 if value.lower() in ("1", "true", "yes", "on") else 0
    return 1 if value else 0


def parse_dt(value, field, end=False):
    """Огноог "YYYY-MM-DD HH:MM:SS" болгож жигдрүүлнэ (буруу бол 400).

    Зөвхөн огноо ирвэл: эхлэл -> 00:00:00, төгсгөл -> 23:59:59 гэж бөглөнө.
    Хоосон/None -> None (хугацааны хязгааргүй гэсэн үг).
    """
    if value in (None, ""):
        return None
    text = str(value).strip().replace("T", " ")
    if len(text) == 10:
        text += " 23:59:59" if end else " 00:00:00"
    if len(text) == 16:
        text += ":00"
    try:
        datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        abort(400, description=(
            f"{field} огноо буруу — 'YYYY-MM-DD' эсвэл 'YYYY-MM-DD HH:MM:SS' хэлбэртэй байна"))
    return text


def load_settings(raw):
    """settings баганы JSON текстийг dict болгоно (эвдэрсэн бол None)."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


# ----------------------------- form -----------------------------
def get_form(conn, fid, include_deleted=False):
    """Маягтын мөрийг буцаана (устгагдсаныг анхдагчаар алгасна)."""
    sql = "SELECT * FROM form WHERE id=?"
    if not include_deleted:
        sql += " AND deleted_at IS NULL"
    return conn.execute(sql, (fid,)).fetchone()


def require_form(conn, fid, include_deleted=False):
    row = get_form(conn, fid, include_deleted)
    if not row:
        bad(conn, "Маягт олдсонгүй", 404)
    return row


def is_open(row, at=None):
    """Тухайн агшинд бөглөх боломжтой эсэх (published + хугацаанд нь багтсан)."""
    if row["status"] != "published":
        return False
    at = at or now_str()
    if row["start_at"] and at < row["start_at"]:
        return False
    if row["end_at"] and at > row["end_at"]:
        return False
    return True


def public_form(row, **extra):
    """Маягтыг JSON-д тохирох хэлбэрээр (0/1 -> true/false) буцаана."""
    out = {
        "id": row["id"],
        "type": row["type"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "show_results": bool(row["show_results"]),
        "one_response": bool(row["one_response"]),
        "is_open": is_open(row),
        "created_by": row["created_by"],
        "updated_by": row["updated_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    out.update(extra)
    return out


def validate_form(conn, data, current=None):
    """type / status / огнооны хүрээг шалгаад жигдрүүлсэн утгуудыг буцаана."""
    ftype = data.get("type") or (current["type"] if current else "survey")
    if ftype not in FORM_TYPES:
        bad(conn, "type буруу. Сонголт: " + ", ".join(FORM_TYPES))
    start = parse_dt(data["start_at"], "start_at") if "start_at" in data else (
        current["start_at"] if current else None)
    end = parse_dt(data["end_at"], "end_at", end=True) if "end_at" in data else (
        current["end_at"] if current else None)
    if start and end and end < start:
        bad(conn, "end_at нь start_at-аас өмнө байж болохгүй")
    return ftype, start, end
