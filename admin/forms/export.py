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
from core.db import get_db
from core.forms_core import form_results, require_form
from core.xlsx import Sheet, as_datetime, xlsx_response

from admin.forms import bp


def _answers(conn, fid, questions):
    """{submission_id: {question_id: утга}} — нэг query-ээр (сонголтуудыг label-ээр нэгтгэнэ)."""
    out = {}
    for r in conn.execute(
            "SELECT a.submission_id, a.question_id, a.text_value, a.numeric_value, o.label "
            "FROM form_answer a JOIN form_submission s ON s.id = a.submission_id "
            "LEFT JOIN form_answer_option ao ON ao.answer_id = a.id "
            "LEFT JOIN form_option o ON o.id = ao.option_id "
            "WHERE s.form_id=? ORDER BY a.submission_id, a.question_id, o.sort_order, o.id",
            (fid,)).fetchall():
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
    conn = get_db()
    try:
        form = require_form(conn, fid)
        qs = conn.execute("SELECT id, title, question_type FROM form_question WHERE form_id=? "
                          "ORDER BY sort_order, id", (fid,)).fetchall()
        submissions = conn.execute("SELECT id, submitted_at FROM form_submission WHERE form_id=? "
                                   "ORDER BY submitted_at, id", (fid,)).fetchall()
        answers = _answers(conn, fid, {q["id"]: q["question_type"] for q in qs})
        results = form_results(conn, fid)
    finally:
        conn.close()
    headers = ["№", "Огноо"] + [q["title"] for q in qs]
    kind = "санал-асуулга" if form["type"] == "poll" else "судалгаа"
    return xlsx_response(f"{kind}-{fid}-үр-дүн", [
        Sheet("Хариултууд", headers, _response_rows(submissions, answers, [q["id"] for q in qs])),
        Sheet("Дүгнэлт", ["Асуулт", "Сонголт / утга", "Тоо", "Хувь (%)", "Дундаж"],
              _summary_rows(results)),
    ])
