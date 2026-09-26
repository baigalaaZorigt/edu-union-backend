"""Үр дүнгийн нэгтгэл — асуулт бүрээр, өдөр бүрээр, нээлттэй хариултууд."""
from core.forms_core.base import CHOICE_TYPES, load_settings
from core.forms_core.questions import scale_range, submission_count


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
    lo, hi = scale_range(settings)
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
