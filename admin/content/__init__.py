"""Порталын динамик цэс ба контентын CRUD (Blueprint).

Бүтэц:
  menu (Цэс) — порталын дээд цэс. `type` нь цэс дээр дарахад юу харагдахыг заана:
      page     — динамик контент хуудас (админ бүрэн удирдана)
      news / survey / poll / contact / home — кодод суусан функциональ хуудсууд
      (news цэс нь `news_category`-оор "Мэдээ"/"Сургалт"-ыг салгаж харуулна)
      external — зөвхөн external_url руу үсэрнэ
  page (Контент хуудас) — type='page' цэс бүрд НЭГ бичлэг (гарчиг, cover, төлөв).
  page_block (Блок) — хуудасны агуулга: text / image / video / file / link блокууд
      ЭРЭМБЭТЭЙГЭЭР дараалж, админ UI дээр ↑↓-ээр солигдоно.

Спекийн /api/page_image|page_file|page_video маршрутууд нь page_block дээрх
төрөлжсөн харагдац юм — өгөгдөл нэг хүснэгтэд (тиймээс нэг л эрэмбэ) хадгалагдана.

Модулиуд (бүгд НЭГ `content` blueprint дээр маршрутаа бүртгэнэ):
    storage  — файлын сан (UPLOAD_DIR, remove_upload)
    common   — цэс/хуудас/блокийн хуваалцсан туслахууд
    menu     — /api/menu
    page     — /api/page
    blocks   — /api/page_block, /api/page_image|page_file|page_video
    upload   — /api/upload, /uploads/content/<нэр>
"""
from flask import Blueprint

bp = Blueprint("content", __name__)

# admin/news.py, admin/settings.py, admin/feedback.py болон тестүүд эдгээрийг
# `admin.content`-оос импортолдог тул энд дахин экспортлоно.
from admin.content.storage import (  # noqa: E402,F401
    DOC_TYPES, IMAGE_TYPES, MAX_DOC_SIZE, MAX_IMAGE_SIZE, UPLOAD_DIR, UPLOAD_URL_PREFIX,
    remove_upload,
)

# Маршрутын модулиудыг bp үүссэний ДАРАА импортлоно — тэд `bp`-г эндээс авна.
from admin.content import menu, page, blocks, upload  # noqa: E402,F401
