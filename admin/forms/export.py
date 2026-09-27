"""Excel экспорт — судалгаа / санал асуулгын үр дүн (спекийн А хувилбар).

    GET /api/admin/forms/<id>/results/export   (form_result.read — үр дүнгийн дэлгэцтэй ижил эрх)

Хоёр хуудас:
  * "Хариултууд" — нэг мөр = нэг бөглөлт; №, Огноо, дараа нь асуулт бүр нэг багана
    (сонголт -> сонголтын нэр(үүд), scale -> тоо, open_text -> текст).
    Хэрэглэгчийн багана ОРОХГҮЙ: үр дүнгийн дэлгэц (GET .../results, .../answers) хариулагчийг
    хэзээ ч тодорхойлдоггүй бөгөөд маягтад "нэртэй" гэсэн тохиргоо байхгүй — файл дэлгэцээс
    илүү ил болохгүй.
  * "Дүгнэлт" — GET .../results-ийн нэгтгэлийг (form_results) шууд бичнэ: сонголт бүрээр
    тоо/хувь, scale-д дундаж ба утга бүрийн тоо, open_text-д хариултын тоо.
"""
from sqlalchemy import select

from core.orm import session
from core.orm.models import FormAnswer, FormAnswerOption, FormOption, FormSubmission
from core.forms_core import form_results, question_rows, require_form
from core.xlsx import Sheet, as_datetime, xlsx_response

from admin.forms import bp


def _answers(fid, questions):
    """{submission_id: {question_id: утга}} — нэг query-ээр (сонголтуудыг label-ээр нэгтгэнэ)."""
    out = {}
    stmt = (select(FormAnswer.submission_id, FormAnswer.question_id, FormAnswer.text_value,
                   FormAnswer.numeric_value, FormOption.label)
            .join(FormSubmission, FormSubmission.id == FormAnswer.submission_id)
            .outerjoin(FormAnswerOption, FormAnswerOption.answer_id == FormAnswer.id)
            .outerjoin(FormOption, FormOption.id == FormAnswerOption.option_id)
            .where(FormSubmission.form_id == fid)
            .order_by(FormAnswer.submission_id, FormAnswer.question_id,
                      FormOption.sort_order, FormOption.id))
    for r in session().execute(stmt).mappings():
        cell = out.setdefault(r["submission_id"], {})
        qtype = questions.get(r["question_id"])
        if qtype in ("single_choice", "multiple_choice"):
            if r["label"] is not None:
                cell.setdefault(r["question_id"], []).append(r["label"])
        elif qtype == "scale":
            v = r["numeric_value"]
            cell[r["question_id"]] = int(v) if v is not None and float(v).is_integer() else v
        else:
            cell[r["question_id"]] = r["text_value"]
    return out


def _response_rows(submissions, answers, qids):
    for i, s in enumerate(submissions, start=1):
        a = answers.get(s["id"], {})
        row = [i, as_datetime(s["submitted_at"])]
        for q in qids:
            v = a.get(q)
            row.append(", ".join(v) if isinstance(v, list) else v)
        yield row


def _summary_rows(results):
    for q in results["questions"]:
        if q["question_type"] in ("single_choice", "multiple_choice"):
            for o in q["results"]:
                yield [q["title"], o["label"], o["count"], o["percent"], None]
        elif q["question_type"] == "scale":
            yield [q["title"], "Дундаж", q["total"], None, q["average"]]
            for d in q["results"]:
                yield [q["title"], str(d["value"]), d["count"], None, None]
        else:
            yield [q["title"], "Нээлттэй хариулт", q["total"], None, None]


@bp.route("/api/admin/forms/<int:fid>/results/export", methods=["GET"])
def export_results(fid):
    form = require_form(fid)
    qs = question_rows(fid)
    submissions = session().execute(
        select(FormSubmission.id, FormSubmission.submitted_at)
        .where(FormSubmission.form_id == fid)
        .order_by(FormSubmission.submitted_at, FormSubmission.id)).mappings().all()
    answers = _answers(fid, {q["id"]: q["question_type"] for q in qs})
    results = form_results(fid)
    headers = ["№", "Огноо"] + [q["title"] for q in qs]
    kind = "санал-асуулга" if form["type"] == "poll" else "судалгаа"
    return xlsx_response(f"{kind}-{fid}-үр-дүн", [
        Sheet("Хариултууд", headers, _response_rows(submissions, answers, [q["id"] for q in qs])),
        Sheet("Дүгнэлт", ["Асуулт", "Сонголт / утга", "Тоо", "Хувь (%)", "Дундаж"],
              _summary_rows(results)),
    ])
