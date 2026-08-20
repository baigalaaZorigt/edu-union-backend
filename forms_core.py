"""Судалгаа / Санал асуулгын хуваалцсан цөм (admin + client site хоёулаа ашиглана).

Нэг л `form` engine — `form.type` нь юу болохыг заана:
    survey — судалгаа (ж: "Багшийн ажлын ачааллын судалгаа")
    poll   — санал асуулга (ж: хуулийн төсөлд санал авах; PDF хавсаргаж болно)

Хүснэгтүүд (db.py-ийн SCHEMA_FORM):
    form -> form_question -> form_option
    form -> form_document (poll-ийн PDF)
    form -> form_submission -> form_answer -> form_answer_option

Энэ модуль нь ЗӨВХӨН домэйний логик: шалгалт, цэвэр хэлбэрт хөрвүүлэлт (public_*),
үр дүнгийн нэгтгэл. HTTP маршрутууд нь:
    admin/forms.py   — /api/admin/...  (админ: үүсгэх, асуулт барих, үр дүн)
    client/forms.py  — /api/portal/... (портал: жагсаалт, бөглөх, илгээх)

Огноо: start_at / end_at / submitted_at бүгд "YYYY-MM-DD HH:MM:SS" хэлбэрээр,
UTC цагаар хадгалагдана (сервер дээрх бусад created_at-тай ижил бүсэд).
"""
import json
import os
from datetime import datetime, timezone

from flask import abort

# --- Санал асуулгын PDF (form_document) ---
# Порталын PDF viewer толгой дамжуулж чаддаггүй тул байршуулсан файлыг
# /uploads/form/ дороос токенгүй үйлчилнэ (auth.py-ийн PUBLIC_PREFIXES).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.environ.get("FORM_UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "form"))
UPLOAD_URL_PREFIX = "/uploads/form/"
MAX_PDF_SIZE = 20 * 1024 * 1024            # PDF ≤ 20 MB
PDF_MAGIC = b"%PDF-"

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


# ----------------------------- Жижиг туслахууд -----------------------------
def now_str():
    """Одоогийн UTC цаг — "YYYY-MM-DD HH:MM:SS" (SQLite-ийн DATE()-тэй нийцнэ)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def bad(conn, message, code=400):
    """Холболтыг хааж байгаад алдаа шидэнэ (холболт алдагдахаас сэргийлнэ)."""
    if conn is not None:
        conn.close()
    abort(code, description=message)


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


# ----------------------------- form_question / form_option -----------------------------
def public_option(row):
    return {"id": row["id"], "question_id": row["question_id"],
            "label": row["label"], "sort_order": row["sort_order"]}


def public_question(row, options=None):
    out = {
        "id": row["id"],
        "form_id": row["form_id"],
        "question_type": row["question_type"],
        "title": row["title"],
        "description": row["description"],
        "is_required": bool(row["is_required"]),
        "sort_order": row["sort_order"],
        "settings": load_settings(row["settings"]),
    }
    if row["question_type"] in CHOICE_TYPES:
        out["options"] = options or []
    return out


def question_list(conn, form_id):
    """Маягтын асуултуудыг эрэмбээр нь, сонголтуудтай нь хамт буцаана."""
    qs = conn.execute(
        "SELECT * FROM form_question WHERE form_id=? ORDER BY sort_order, id",
        (form_id,)).fetchall()
    if not qs:
        return []
    opts = {}
    ph = ", ".join("?" * len(qs))
    for o in conn.execute(
            f"SELECT * FROM form_option WHERE question_id IN ({ph}) "
            "ORDER BY sort_order, id", [q["id"] for q in qs]).fetchall():
        opts.setdefault(o["question_id"], []).append(public_option(o))
    return [public_question(q, opts.get(q["id"])) for q in qs]


def one_question(conn, qid):
    """Нэг асуултыг сонголтуудтай нь буцаана (байхгүй бол None)."""
    row = conn.execute("SELECT * FROM form_question WHERE id=?", (qid,)).fetchone()
    if not row:
        return None
    opts = [public_option(o) for o in conn.execute(
        "SELECT * FROM form_option WHERE question_id=? ORDER BY sort_order, id",
        (qid,)).fetchall()]
    return public_question(row, opts)


def validate_question(conn, data, current=None):
    """question_type ба settings-ийг шалгана -> (төрөл, settings JSON текст)."""
    qtype = data.get("question_type") or (current["question_type"] if current else None)
    if qtype not in QUESTION_TYPES:
        bad(conn, "question_type буруу. Сонголт: " + ", ".join(QUESTION_TYPES))

    settings = data.get("settings", "__keep__")
    if settings == "__keep__":
        settings = load_settings(current["settings"]) if current else None
    if settings is not None and not isinstance(settings, dict):
        bad(conn, "settings нь объект (JSON) байх ёстой")

    if qtype == "scale":
        settings = dict(settings or {})
        lo = settings.get("min", SCALE_MIN)
        hi = settings.get("max", 5)
        if not isinstance(lo, int) or not isinstance(hi, int):
            bad(conn, "scale асуултын settings.min / settings.max нь бүхэл тоо байна")
        if lo >= hi or lo < SCALE_MIN or hi > SCALE_MAX:
            bad(conn, f"scale хүрээ буруу — {SCALE_MIN} <= min < max <= {SCALE_MAX}")
        settings["min"], settings["max"] = lo, hi
    return qtype, (json.dumps(settings, ensure_ascii=False) if settings else None)


def next_sort(conn, table, column, value):
    """Тухайн эцэг доторх дараагийн эрэмбийн дугаар."""
    return conn.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 FROM {table} WHERE {column}=?",
        (value,)).fetchone()[0]


def insert_options(conn, question_id, options):
    """Сонголтуудыг эрэмбэтэйгээр нэмнэ (жагсаалтын дараалал = sort_order)."""
    if not options:
        return
    if not isinstance(options, list):
        bad(conn, "options нь жагсаалт байх ёстой")
    now = now_str()
    for i, opt in enumerate(options, start=1):
        label = opt.get("label") if isinstance(opt, dict) else opt
        if not label or not str(label).strip():
            bad(conn, "Сонголт бүр label-тэй байх ёстой")
        order = opt.get("sort_order") if isinstance(opt, dict) else None
        conn.execute(
            "INSERT INTO form_option(question_id, label, sort_order, created_at) "
            "VALUES (?,?,?,?)", (question_id, str(label).strip(), order or i, now))


def insert_question(conn, form_id, data):
    """Асуулт (+ сонголтууд) нэмээд шинэ id-г буцаана."""
    qtype, settings = validate_question(conn, data)
    if not (data.get("title") or "").strip():
        bad(conn, "title (асуултын текст) шаардлагатай")
    if qtype in CHOICE_TYPES and not data.get("options"):
        bad(conn, f"{qtype} асуултад дор хаяж нэг options шаардлагатай")
    now = now_str()
    cur = conn.execute(
        "INSERT INTO form_question(form_id, question_type, title, description, "
        "is_required, sort_order, settings, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (form_id, qtype, data["title"].strip(), data.get("description"),
         _flag(data.get("is_required"), 0),
         data.get("sort_order") or next_sort(conn, "form_question", "form_id", form_id),
         settings, now, now))
    insert_options(conn, cur.lastrowid, data.get("options"))
    return cur.lastrowid


# ----------------------------- Илгээмж (submission) -----------------------------
def has_submitted(conn, form_id, user_id):
    """Тухайн хэрэглэгч бөглөсөн эсэх. Зочин (user_id=None) бол үргэлж False."""
    if not user_id:
        return False
    return bool(conn.execute(
        "SELECT 1 FROM form_submission WHERE form_id=? AND user_id=?",
        (form_id, user_id)).fetchone())


def submission_count(conn, form_id):
    return conn.execute(
        "SELECT COUNT(*) FROM form_submission WHERE form_id=?", (form_id,)).fetchone()[0]


# ----------------------------- Үр дүнгийн нэгтгэл -----------------------------
def _choice_results(conn, question_id):
    """Сонголт бүрийн тоо ба хувь. Хувийн суурь = тухайн асуултад хариулсан хүн."""
    total = conn.execute(
        "SELECT COUNT(*) FROM form_answer WHERE question_id=?", (question_id,)).fetchone()[0]
    out = []
    for r in conn.execute(
            "SELECT o.id, o.label, COUNT(ao.id) AS cnt FROM form_option o "
            "LEFT JOIN form_answer_option ao ON ao.option_id = o.id "
            "WHERE o.question_id=? GROUP BY o.id, o.label ORDER BY o.sort_order, o.id",
            (question_id,)).fetchall():
        out.append({"option_id": r["id"], "label": r["label"], "count": r["cnt"],
                    "percent": round(r["cnt"] * 100.0 / total, 1) if total else 0})
    return total, out


def _scale_results(conn, question_id, settings):
    """1..5 гэх мэт үнэлгээний тархалт + дундаж."""
    counts = {r["v"]: r["cnt"] for r in conn.execute(
        "SELECT CAST(numeric_value AS INTEGER) AS v, COUNT(*) AS cnt FROM form_answer "
        "WHERE question_id=? AND numeric_value IS NOT NULL GROUP BY v", (question_id,)).fetchall()}
    row = conn.execute(
        "SELECT AVG(numeric_value) AS avg, COUNT(*) AS cnt FROM form_answer "
        "WHERE question_id=? AND numeric_value IS NOT NULL", (question_id,)).fetchone()
    lo = (settings or {}).get("min", SCALE_MIN)
    hi = (settings or {}).get("max", 5)
    # Хариулт ирээгүй утгыг ч 0-ээр буцаана — график завсаргүй харагдана.
    values = sorted(set(range(lo, hi + 1)) | set(counts))
    return row["cnt"], (round(row["avg"], 2) if row["avg"] is not None else None), [
        {"value": v, "count": counts.get(v, 0)} for v in values]


def form_results(conn, form_id):
    """Спекийн 19/20-р хэсгийн үр дүнгийн бүтэц (асуулт бүрээр нэгтгэсэн)."""
    total = submission_count(conn, form_id)
    out = []
    for q in conn.execute(
            "SELECT * FROM form_question WHERE form_id=? ORDER BY sort_order, id",
            (form_id,)).fetchall():
        item = {"question_id": q["id"], "title": q["title"],
                "question_type": q["question_type"]}
        if q["question_type"] in CHOICE_TYPES:
            answered, item["results"] = _choice_results(conn, q["id"])
            item["total"] = answered
        elif q["question_type"] == "scale":
            answered, avg, dist = _scale_results(conn, q["id"], load_settings(q["settings"]))
            item.update(total=answered, average=avg, results=dist)
        else:                                   # open_text — график хэрэггүй
            item["total"] = conn.execute(
                "SELECT COUNT(*) FROM form_answer WHERE question_id=? "
                "AND text_value IS NOT NULL", (q["id"],)).fetchone()[0]
        out.append(item)
    return {"form_id": form_id, "total_responses": total, "questions": out}


def open_text_answers(conn, question_id, limit=None, offset=0):
    """Нээлттэй асуултын бичвэр хариултууд (шинэ нь эхэндээ)."""
    sql = ("SELECT a.id, a.text_value AS text, s.submitted_at FROM form_answer a "
           "JOIN form_submission s ON s.id = a.submission_id "
           "WHERE a.question_id=? AND a.text_value IS NOT NULL "
           "ORDER BY s.submitted_at DESC, a.id DESC")
    args = [question_id]
    if limit:
        sql += " LIMIT ? OFFSET ?"
        args += [limit, offset]
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def results_trend(conn, form_id):
    """Өдөр бүрийн хариултын тоо (админ dashboard-ийн график)."""
    return [{"date": r["date"], "total": r["total"]} for r in conn.execute(
        "SELECT DATE(submitted_at) AS date, COUNT(*) AS total FROM form_submission "
        "WHERE form_id=? GROUP BY DATE(submitted_at) ORDER BY date", (form_id,)).fetchall()]


# ----------------------------- form_document (PDF) -----------------------------
def public_document(row):
    return {"id": row["id"], "form_id": row["form_id"], "file_name": row["file_name"],
            "file_path": row["file_path"], "url": row["file_path"],
            "mime_type": row["mime_type"], "file_size": row["file_size"],
            "created_at": row["created_at"]}


def document_list(conn, form_id):
    return [public_document(r) for r in conn.execute(
        "SELECT * FROM form_document WHERE form_id=? ORDER BY id", (form_id,)).fetchall()]


def remove_upload(file_path):
    """Байршуулсан PDF-г дискнээс арилгана (зөвхөн өөрсдийн угтвартай замыг)."""
    if not file_path or not file_path.startswith(UPLOAD_URL_PREFIX):
        return
    path = os.path.join(UPLOAD_DIR, os.path.basename(file_path))
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass        # диск дээрээс арилгаж чадаагүй ч DB-гийн мөр устсан хэвээр
