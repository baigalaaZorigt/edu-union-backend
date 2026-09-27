"""Үр дүнгийн нэгтгэл — асуулт бүрээр, өдөр бүрээр, нээлттэй хариултууд."""
from sqlalchemy import func, select

from core.orm import session
from core.orm.models import FormAnswer, FormAnswerOption, FormOption, FormSubmission
from core.forms_core.base import CHOICE_TYPES, load_settings
from core.forms_core.questions import question_rows, scale_range, submission_count


# ----------------------------- Үр дүнгийн нэгтгэл -----------------------------
def _choice_results(question_id):
    """Сонголт бүрийн тоо ба хувь. Хувийн суурь = тухайн асуултад хариулсан хүн."""
    s = session()
    total = s.scalar(select(func.count()).select_from(FormAnswer)
                     .where(FormAnswer.question_id == question_id))
    out = []
    for oid, label, cnt in s.execute(
            select(FormOption.id, FormOption.label, func.count(FormAnswerOption.id))
            .outerjoin(FormAnswerOption, FormAnswerOption.option_id == FormOption.id)
            .where(FormOption.question_id == question_id)
            .group_by(FormOption.id, FormOption.label)
            .order_by(FormOption.sort_order, FormOption.id)):
        out.append({"option_id": oid, "label": label, "count": cnt,
                    "percent": round(cnt * 100.0 / total, 1) if total else 0})
    return total, out


def _scale_results(question_id, settings):
    """1..5 гэх мэт үнэлгээний тархалт + дундаж."""
    values = list(session().scalars(
        select(FormAnswer.numeric_value).where(FormAnswer.question_id == question_id,
                                               FormAnswer.numeric_value.is_not(None))))
    counts = {}
    for v in values:
        counts[int(v)] = counts.get(int(v), 0) + 1
    avg = round(sum(values) / len(values), 2) if values else None
    lo, hi = scale_range(settings)
    # Хариулт ирээгүй утгыг ч 0-ээр буцаана — график завсаргүй харагдана.
    keys = sorted(set(range(lo, hi + 1)) | set(counts))
    return len(values), avg, [{"value": v, "count": counts.get(v, 0)} for v in keys]


def form_results(form_id):
    """Спекийн 19/20-р хэсгийн үр дүнгийн бүтэц (асуулт бүрээр нэгтгэсэн)."""
    total = submission_count(form_id)
    out = []
    for q in question_rows(form_id):
        item = {"question_id": q["id"], "title": q["title"],
                "question_type": q["question_type"]}
        if q["question_type"] in CHOICE_TYPES:
            answered, item["results"] = _choice_results(q["id"])
            item["total"] = answered
        elif q["question_type"] == "scale":
            answered, avg, dist = _scale_results(q["id"], load_settings(q["settings"]))
            item.update(total=answered, average=avg, results=dist)
        else:                                   # open_text — график хэрэггүй
            item["total"] = session().scalar(
                select(func.count()).select_from(FormAnswer)
                .where(FormAnswer.question_id == q["id"], FormAnswer.text_value.is_not(None)))
        out.append(item)
    return {"form_id": form_id, "total_responses": total, "questions": out}


def open_text_answers(question_id, limit=None, offset=0):
    """Нээлттэй асуултын бичвэр хариултууд (шинэ нь эхэндээ)."""
    stmt = (select(FormAnswer.id, FormAnswer.text_value.label("text"), FormSubmission.submitted_at)
            .join(FormSubmission, FormSubmission.id == FormAnswer.submission_id)
            .where(FormAnswer.question_id == question_id, FormAnswer.text_value.is_not(None))
            .order_by(FormSubmission.submitted_at.desc(), FormAnswer.id.desc()))
    if limit:
        stmt = stmt.limit(limit).offset(offset)
    return [dict(r) for r in session().execute(stmt).mappings()]


def results_trend(form_id):
    """Өдөр бүрийн хариултын тоо (админ dashboard-ийн график).

    submitted_at нь "YYYY-MM-DD HH:MM:SS" текст — өдрийг эхний 10 тэмдэгтээр Python-д
    бүлэглэнэ (DB-ийн DATE() функцээс хамааралгүй).
    """
    days = {}
    for ts in session().scalars(select(FormSubmission.submitted_at)
                                .where(FormSubmission.form_id == form_id)):
        day = ts[:10] if ts else None
        days[day] = days.get(day, 0) + 1
    return [{"date": d, "total": days[d]}
            for d in sorted(days, key=lambda d: (d is not None, d or ""))]
