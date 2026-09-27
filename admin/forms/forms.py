"""form (Маягт) — жагсаалт, үүсгэх, засах, устгах, нийтлэх, хаах."""

from flask import jsonify, request
from sqlalchemy import delete, func, or_, select, update

from core.helpers import require, json_body
from core.orm import session
from core.orm.models import Form, FormQuestion, FormSubmission
from core.forms_core import (
    FORM_FIELDS, FORM_STATUSES, bad, current_user_id, now_str, public_form, insert_question,
    require_form, submission_count, validate_form, _flag,
)

from admin.forms import bp
from admin.forms.common import MAX_PER_PAGE, _detail_response, _set_status


# ============================ form (Маягт) ============================
@bp.route("/api/admin/forms", methods=["GET"])
def list_forms():
    """Маягтын жагсаалт. Шүүлт: ?type= &status= &search= &page= &per_page=

    Буцаалт: {items, total, page, per_page, pages}
    """
    s = session()
    conds = [Form.deleted_at.is_(None)]
    if request.args.get("type"):
        conds.append(Form.type == request.args["type"])
    if request.args.get("status"):
        conds.append(Form.status == request.args["status"])
    search = (request.args.get("search") or "").strip()
    if search:
        conds.append(or_(Form.title.like(f"%{search}%"), Form.description.like(f"%{search}%")))

    total = s.scalar(select(func.count()).select_from(Form).where(*conds))
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        bad("page / per_page нь тоо байх ёстой")
    responses = (select(func.count()).select_from(FormSubmission)
                 .where(FormSubmission.form_id == Form.id).scalar_subquery())
    questions = (select(func.count()).select_from(FormQuestion)
                 .where(FormQuestion.form_id == Form.id).scalar_subquery())
    data = s.execute(
        select(Form, responses.label("total_responses"), questions.label("total_questions"))
        .where(*conds).order_by(Form.id.desc())
        .limit(per_page).offset((page - 1) * per_page)).all()
    items = [public_form(f.to_dict(), total_responses=tr, total_questions=tq)
             for f, tr, tq in data]
    return jsonify(items=items, total=total, page=page, per_page=per_page,
                   pages=(total + per_page - 1) // per_page)


@bp.route("/api/admin/forms/<int:fid>", methods=["GET"])
def get_form_detail(fid):
    """Маягт + асуултууд + сонголтууд + хавсаргасан PDF."""
    require_form(fid)
    return _detail_response(fid)


@bp.route("/api/admin/forms", methods=["POST"])
def create_form():
    """Маягт үүсгэх. Заавал: title. Сонголтоор questions[] хамт илгээж болно."""
    data = request.get_json(silent=True)
    require(data, ["title"])
    ftype, start, end = validate_form(data)
    now = now_str()
    s = session()
    form = Form(type=ftype, title=data["title"], description=data.get("description"),
                status="draft", start_at=start, end_at=end,
                show_results=_flag(data.get("show_results")),
                one_response=_flag(data.get("one_response")),
                created_by=current_user_id(), created_at=now, updated_at=now)
    s.add(form)
    s.flush()
    fid = form.id
    for q in (data.get("questions") or []):     # маягтыг асуултуудтай нь нэг дор
        insert_question(fid, q)
    s.commit()
    return _detail_response(fid, 201)


@bp.route("/api/admin/forms/<int:fid>", methods=["PUT", "PATCH"])
def update_form(fid):
    """Маягт засах (хэсэгчилсэн). status-г мөн энд эсвэл publish/close-оор солино."""
    data = json_body()
    current = require_form(fid)
    ftype, start, end = validate_form(data, current)
    normalized = {"type": ftype, "start_at": start, "end_at": end}
    values = {}
    for f in FORM_FIELDS:
        if f not in data:
            continue
        if f in normalized:
            values[f] = normalized[f]
        elif f in ("show_results", "one_response"):
            values[f] = _flag(data[f])
        else:
            values[f] = data[f]
    if "status" in data:
        if data["status"] not in FORM_STATUSES:
            bad("status буруу. Сонголт: " + ", ".join(FORM_STATUSES))
        values["status"] = data["status"]
    if not values:
        bad("Шинэчлэх талбар алга")
    values.update(updated_by=current_user_id(), updated_at=now_str())
    s = session()
    s.execute(update(Form).where(Form.id == fid).values(**values))
    s.commit()
    return _detail_response(fid)


@bp.route("/api/admin/forms/<int:fid>", methods=["DELETE"])
def delete_form(fid):
    """Маягт устгах.

    Хариулт ИРЭЭГҮЙ бол устгана (асуулт/сонголт/PDF нь каскадаар) -> soft=False.
    Хариулт ИРСЭН бол зөвхөн маягтыг архивлана (үр дүн нь уншигдсаар) -> soft=True.
    ?hard=1 өгвөл хариулттай ч гэсэн каскадтай устгана.
    Бүх устгал soft delete (core/orm/soft.py) — мөр, PDF файл хадгалагдана.
    """
    require_form(fid)
    s = session()
    hard = request.args.get("hard") in ("1", "true", "True")
    if not hard and submission_count(fid):
        s.execute(update(Form).where(Form.id == fid).values(
            deleted_at=now_str(), updated_by=current_user_id()))
        s.commit()
        return jsonify(deleted=fid, soft=True,
                       message="Хариулттай тул архивлав (устгасан төлөвт шилжив)")
    s.execute(delete(Form).where(Form.id == fid))       # soft delete (асуулт/PDF каскадаар)
    s.commit()
    return jsonify(deleted=fid, soft=False)


@bp.route("/api/admin/forms/<int:fid>/publish", methods=["POST"])
def publish_form(fid):
    """Маягтыг нийтлэх — порталд харагдаж, бөглөх боломжтой болно."""
    return _set_status(fid, "published")


@bp.route("/api/admin/forms/<int:fid>/close", methods=["POST"])
def close_form(fid):
    """Маягтыг хаах — шинэ хариулт хүлээж авахгүй (үр дүн хэвээр)."""
    return _set_status(fid, "closed")
