"""Судалгаа / Санал асуулгын хуваалцсан цөм (admin + client site хоёулаа ашиглана).

Нэг л `form` engine — `form.type` нь юу болохыг заана:
    survey — судалгаа (ж: "Багшийн ажлын ачааллын судалгаа")
    poll   — санал асуулга (ж: хуулийн төсөлд санал авах; PDF хавсаргаж болно)

Хүснэгтүүд (db.py-ийн SCHEMA_FORM):
    form -> form_question -> form_option
    form -> form_document (poll-ийн PDF)
    form -> form_submission -> form_answer -> form_answer_option

Энэ модуль нь ЗӨВХӨН домэйний логик: шалгалт (маягт, асуулт, PDF), цэвэр хэлбэрт
хөрвүүлэлт (public_*), үр дүнгийн нэгтгэл. HTTP маршрутууд нь:
    admin/forms/     — /api/admin/...  (админ: үүсгэх, асуулт барих, үр дүн)
    client/forms.py  — /api/portal/... (портал: жагсаалт, бөглөх, илгээх)

Огноо: start_at / end_at / submitted_at бүгд "YYYY-MM-DD HH:MM:SS" хэлбэрээр,
UTC цагаар хадгалагдана (сервер дээрх бусад created_at-тай ижил бүсэд).

Модулиуд (бүх нэрийг эндээс `from core.forms_core import ...` гэж импортлоно):
    base       — тогтмолууд, жижиг туслахууд, form
    questions  — form_question / form_option, илгээмж
    results    — үр дүнгийн нэгтгэл
    documents  — poll-ийн PDF (form_document)
"""
from core.helpers import now_str  # noqa: F401  (хуучин импортуудад зориулсан)
from core.forms_core.base import (  # noqa: F401
    CHOICE_TYPES, FORM_FIELDS, FORM_STATUSES, FORM_TYPES, QUESTION_FIELDS, QUESTION_TYPES,
    SCALE_DEFAULT_MAX, SCALE_MAX, SCALE_MIN,
    _flag, bad, current_user_id, get_form, is_open, load_settings, parse_dt, public_form,
    require_form, validate_form,
)
from core.forms_core.questions import (  # noqa: F401
    has_submitted, insert_options, insert_question, next_sort, one_question, public_option,
    public_question, question_list, scale_range, submission_count, validate_question,
)
from core.forms_core.results import (  # noqa: F401
    form_results, open_text_answers, results_trend,
)
from core.forms_core.documents import (  # noqa: F401
    MAX_PDF_SIZE, PDF_MAGIC, UPLOAD_DIR, UPLOAD_URL_PREFIX,
    document_list, public_document, remove_upload, validate_pdf,
)
