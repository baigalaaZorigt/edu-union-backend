"""Асуулт (form_question), сонголт (form_option), илгээмжийн тоолол."""
import json

from core.helpers import insert_row, now_str
from core.forms_core.base import (
    CHOICE_TYPES, QUESTION_TYPES, SCALE_DEFAULT_MAX, SCALE_MAX, SCALE_MIN, _flag, bad, load_settings,
)


# ----------------------------- form_question / form_option -----------------------------
def public_option(row):
    return {"id": row["id"], "question_id": row["question_id"],
            "label": row["label"], "sort_order": row["sort_order"],
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


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
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if row["question_type"] in CHOICE_TYPES:
        out["options"] = options or []
    return out


def _options_by_question(conn, question_ids):
    """{question_id: [сонголт, ...]} — асуултуудын сонголтыг нэг query-гээр эрэмбээр нь."""
    if not question_ids:
        return {}
    opts = {}
    ph = ", ".join("?" * len(question_ids))
    for o in conn.execute(
            f"SELECT * FROM form_option WHERE question_id IN ({ph}) "
            "ORDER BY sort_order, id", question_ids).fetchall():
        opts.setdefault(o["question_id"], []).append(public_option(o))
    return opts


def question_list(conn, form_id):
    """Маягтын асуултуудыг эрэмбээр нь, сонголтуудтай нь хамт буцаана."""
    qs = conn.execute(
        "SELECT * FROM form_question WHERE form_id=? ORDER BY sort_order, id",
        (form_id,)).fetchall()
    opts = _options_by_question(conn, [q["id"] for q in qs])
    return [public_question(q, opts.get(q["id"])) for q in qs]


def one_question(conn, qid):
    """Нэг асуултыг сонголтуудтай нь буцаана (байхгүй бол None)."""
    row = conn.execute("SELECT * FROM form_question WHERE id=?", (qid,)).fetchone()
    if not row:
        return None
    return public_question(row, _options_by_question(conn, [qid]).get(qid))


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
        lo, hi = scale_range(settings)
        if not isinstance(lo, int) or not isinstance(hi, int):
            bad(conn, "scale асуултын settings.min / settings.max нь бүхэл тоо байна")
        if lo >= hi or lo < SCALE_MIN or hi > SCALE_MAX:
            bad(conn, f"scale хүрээ буруу — {SCALE_MIN} <= min < max <= {SCALE_MAX}")
        settings["min"], settings["max"] = lo, hi
    return qtype, (json.dumps(settings, ensure_ascii=False) if settings else None)


def scale_range(settings):
    """scale асуултын (min, max) — settings-д байхгүй бол анхдагч 1..5."""
    settings = settings or {}
    return settings.get("min", SCALE_MIN), settings.get("max", SCALE_DEFAULT_MAX)


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
        insert_row(conn, "form_option", {"question_id": question_id,
                                         "label": str(label).strip(),
                                         "sort_order": order or i, "created_at": now})


def insert_question(conn, form_id, data):
    """Асуулт (+ сонголтууд) нэмээд шинэ id-г буцаана."""
    qtype, settings = validate_question(conn, data)
    if not (data.get("title") or "").strip():
        bad(conn, "title (асуултын текст) шаардлагатай")
    if qtype in CHOICE_TYPES and not data.get("options"):
        bad(conn, f"{qtype} асуултад дор хаяж нэг options шаардлагатай")
    now = now_str()
    qid = insert_row(conn, "form_question", {
        "form_id": form_id, "question_type": qtype, "title": data["title"].strip(),
        "description": data.get("description"),
        "is_required": _flag(data.get("is_required"), 0),
        "sort_order": data.get("sort_order")
        or next_sort(conn, "form_question", "form_id", form_id),
        "settings": settings, "created_at": now, "updated_at": now})
    insert_options(conn, qid, data.get("options"))
    return qid


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
