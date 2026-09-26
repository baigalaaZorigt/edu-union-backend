"""Судалгаа / Санал асуулгын АДМИН тал (Blueprint).

Замын угтвар: /api/admin/... — маягт үүсгэх, асуулт барих, PDF хавсаргах, үр дүн харах.
Порталын тал (жагсаалт, бөглөх, илгээх) нь client/forms.py дотор.

Урсгал:
    Маягт үүсгэх -> Асуулт нэмэх -> Сонголт нэмэх -> Хугацаа тавих -> Нийтлэх (publish)
                 -> (хариултууд цуглана) -> Үр дүн харах -> Хаах (close)

Хариулт ирсэн маягтын БҮТЦИЙГ (асуулт/сонголт устгах, сонголт солих) өөрчлөхийг
хориглоно — өмнөх хариултууд утгаа алдахаас сэргийлнэ (409).

Модулиуд (бүгд НЭГ `admin_forms` blueprint дээр маршрутаа бүртгэнэ):
    common     — хуваалцсан туслахууд (_lock_if_answered, _detail_response, ...)
    forms      — /api/admin/forms (+ publish / close)
    questions  — /api/admin/forms/<id>/questions, /api/admin/questions/<id>
    options    — /api/admin/questions/<id>/options, /api/admin/options/<id>
    documents  — /api/admin/forms/<id>/document(s), /api/admin/documents/<id>, /uploads/form/
    results    — /api/admin/forms/<id>/results(/trend), .../questions/<id>/answers
"""
from flask import Blueprint

bp = Blueprint("admin_forms", __name__)

# Маршрутын модулиудыг bp үүссэний ДАРАА импортлоно — тэд `bp`-г эндээс авна.
from admin.forms import (  # noqa: E402,F401
    forms, questions, options, documents, results,
)
