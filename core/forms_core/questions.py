"""Асуулт (form_question), сонголт (form_option), илгээмжийн тоолол."""
import json

from sqlalchemy import func, select

from core.helpers import now_str
from core.orm import session
from core.orm.models import FormOption, FormQuestion, FormSubmission
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


def _options_by_question(question_ids):
    """{question_id: [сонголт, ...]} — асуултуудын сонголтыг нэг query-гээр эрэмбээр нь."""
    if not question_ids:
        return {}
    opts = {}
    for o in session().scalars(
            select(FormOption).where(FormOption.question_id.in_(question_ids))
            .order_by(FormOption.sort_order, FormOption.id)):
        opts.setdefault(o.question_id, []).append(public_option(o.to_dict()))
    return opts


def question_rows(form_id):
    """Маягтын асуултын мөрүүд (dict) эрэмбээр нь."""
    return [q.to_dict() for q in session().scalars(
        select(FormQuestion).where(FormQuestion.form_id == form_id)
        .order_by(FormQuestion.sort_order, FormQuestion.id))]


def question_list(form_id):
    """Маягтын асуултуудыг эрэмбээр нь, сонголтуудтай нь хамт буцаана."""
    qs = question_rows(form_id)
    opts = _options_by_question([q["id"] for q in qs])
    return [public_question(q, opts.get(q["id"])) for q in qs]


def one_question(qid):
    """Нэг асуултыг сонголтуудтай нь буцаана (байхгүй бол None)."""
    obj = session().get(FormQuestion, qid)
    if obj is None:
        return None
    return public_question(obj.to_dict(), _options_by_question([qid]).get(qid))


def validate_question(data, current=None):
    """question_type ба settings-ийг шалгана -> (төрөл, settings JSON текст)."""
    qtype = data.get("question_type") or (current["question_type"] if current else None)
    if qtype not in QUESTION_TYPES:
        bad("question_type буруу. Сонголт: " + ", ".join(QUESTION_TYPES))

    settings = data.get("settings", "__keep__")
    if settings == "__keep__":
        settings = load_settings(current["settings"]) if current else None
    if settings is not None and not isinstance(settings, dict):
        bad("settings нь объект (JSON) байх ёстой")

    if qtype == "scale":
        settings = dict(settings or {})
        lo, hi = scale_range(settings)
        if not isinstance(lo, int) or not isinstance(hi, int):
            bad("scale асуултын settings.min / settings.max нь бүхэл тоо байна")
        if lo >= hi or lo < SCALE_MIN or hi > SCALE_MAX:
            bad(f"scale хүрээ буруу — {SCALE_MIN} <= min < max <= {SCALE_MAX}")
        settings["min"], settings["max"] = lo, hi
    return qtype, (json.dumps(settings, ensure_ascii=False) if settings else None)


def scale_range(settings):
    """scale асуултын (min, max) — settings-д байхгүй бол анхдагч 1..5."""
    settings = settings or {}
    return settings.get("min", SCALE_MIN), settings.get("max", SCALE_DEFAULT_MAX)


def next_sort(model, parent_column, value):
    """Тухайн эцэг доторх дараагийн эрэмбийн дугаар (ж: next_sort(FormOption, FormOption.question_id, 5))."""
    return session().scalar(
        select(func.coalesce(func.max(model.sort_order), 0) + 1).where(parent_column == value))


def insert_options(question_id, options):
    """Сонголтуудыг эрэмбэтэйгээр нэмнэ (жагсаалтын дараалал = sort_order)."""
    if not options:
        return
    if not isinstance(options, list):
        bad("options нь жагсаалт байх ёстой")
    now = now_str()
    for i, opt in enumerate(options, start=1):
        label = opt.get("label") if isinstance(opt, dict) else opt
        if not label or not str(label).strip():
            bad("Сонголт бүр label-тэй байх ёстой")
        order = opt.get("sort_order") if isinstance(opt, dict) else None
        session().add(FormOption(question_id=question_id, label=str(label).strip(),
                                 sort_order=order or i, created_at=now))
    session().flush()


def insert_question(form_id, data):
    """Асуулт (+ сонголтууд) нэмээд шинэ id-г буцаана."""
    qtype, settings = validate_question(data)
    if not (data.get("title") or "").strip():
        bad("title (асуултын текст) шаардлагатай")
    if qtype in CHOICE_TYPES and not data.get("options"):
        bad(f"{qtype} асуултад дор хаяж нэг options шаардлагатай")
    now = now_str()
    q = FormQuestion(
        form_id=form_id, question_type=qtype, title=data["title"].strip(),
        description=data.get("description"),
        is_required=_flag(data.get("is_required"), 0),
        sort_order=data.get("sort_order")
        or next_sort(FormQuestion, FormQuestion.form_id, form_id),
        settings=settings, created_at=now, updated_at=now)
    session().add(q)
    session().flush()
    insert_options(q.id, data.get("options"))
    return q.id


# ----------------------------- Илгээмж (submission) -----------------------------
def has_submitted(form_id, user_id):
    """Тухайн хэрэглэгч бөглөсөн эсэх. Зочин (user_id=None) бол үргэлж False."""
    if not user_id:
        return False
    return session().scalar(
        select(FormSubmission.id).where(FormSubmission.form_id == form_id,
                                        FormSubmission.user_id == user_id).limit(1)) is not None


def submission_count(form_id):
    return session().scalar(
        select(func.count()).select_from(FormSubmission).where(FormSubmission.form_id == form_id))
