"""Оруулах цэг — Flask апп үүсгэж, хоёр site-ийн blueprint-уудыг холбоно.

    python run.py                 # dev сервер (default порт 5001)
    FLASK_DEBUG=1 python run.py   # auto-reload/debug-тэй dev сервер
    gunicorn run:app              # production (Render г.м.) — `app` объектыг ачаална

Порт нь PORT орчны хувьсагчаас (Render/Heroku тохируулна), эс бөгөөс 5001.

Бүтэц:
  client/  — үйлчлүүлэгчийн site (засаг захиргаа + үйлдвэрчний эвлэлийн өгөгдөл)
  admin/   — удирдлагын site (хэрэглэгч / эрх / дүр, порталын цэс ба контент)
  db.py, helpers.py — хоёр site-ийн хуваалцсан суурь (DB, туслахууд)
"""
import os

from flask import Flask, request

from db import ensure_seeded
from helpers import register_error_handlers
from auth import require_auth, SECRET_KEY

# --- client site ---
from client.admin_units import bp as admin_units_bp
from client.union import bp as union_bp, MAX_FILE_SIZE
from client.forms import bp as portal_forms_bp

# --- admin site ---
from admin.users import bp as users_bp
from admin.content import bp as content_bp
from admin.forms import bp as admin_forms_bp


# Порталын client өөр домэйн/портоос (ж: React dev сервер :3000) хандах тул
# CORS-ийн толгойг өөрсдөө нэмнэ — нэмэлт сан суулгах шаардлагагүй.
# Нэвтрэлт нь cookie БИШ Bearer токен дээр суурилдаг тул `*` нь CSRF үүсгэхгүй.
# Нарийсгах бол CORS_ORIGINS орчны хувьсагчид таслалаар тусгаарлан жагсаана:
#   CORS_ORIGINS="https://portal.example.mn,https://admin.example.mn"
CORS_ORIGINS = [o.strip() for o in
                os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]


def add_cors_headers(response):
    """Хариу бүрд CORS толгой нэмнэ (Origin ирсэн буюу браузераас ирсэн үед)."""
    origin = request.headers.get("Origin")
    if not origin:
        return response                       # curl/сервер хоорондын дуудлага
    if "*" in CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin in CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"   # кэш origin тус бүрээр салгана
    else:
        return response                       # зөвшөөрөөгүй эх — толгой нэмэхгүй
    response.headers["Access-Control-Allow-Methods"] = \
        "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"   # preflight-г 1 хоног кэшлэнэ
    return response


def create_app():
    """Flask апп үүсгэж, тохиргоо ба blueprint-уудыг холбоно."""
    app = Flask(__name__)
    app.json.ensure_ascii = False  # Кирилл үсгийг escape хийлгүй буцаах
    app.secret_key = SECRET_KEY
    # Хүсэлтийн нийт хэмжээний тааз. Файл ТУС БҮР 10 MB-аар хязгаарлагдана
    # (client/union.py), энэ нь олон файлыг нэг дор илгээх боломж үлдээж, сервер
    # рүү хэт том хүсэлт ирэхээс хамгаална (хэтэрвэл 413 -> {"error": ...}).
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE * 5

    # Нэвтрэлт + эрхийн хяналт: /api/login болон /api/portal/, /uploads/-аас бусад
    # бүх хүсэлтэд токен + эрх шаардана (auth.py-ийн PUBLIC_* -ыг үзнэ үү).
    app.before_request(require_auth)
    app.after_request(add_cors_headers)   # браузерын client өөр домэйнээс хандана

    # Client site — засаг захиргаа + үйлдвэрчний эвлэл
    app.register_blueprint(admin_units_bp)
    app.register_blueprint(union_bp)
    app.register_blueprint(portal_forms_bp)   # /api/portal/... — судалгаа бөглөх

    # Admin site — хэрэглэгчийн удирдлага + порталын цэс/контент
    app.register_blueprint(users_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(admin_forms_bp)    # /api/admin/... — судалгаа/санал асуулга

    register_error_handlers(app)  # 400/401/403/404/409 -> {"error": ...} JSON
    ensure_seeded()               # схем + хоосон бол автоматаар seed (Render дээр ч ажиллана)
    return app


app = create_app()


if __name__ == "__main__":
    # Render/Heroku зэрэг платформ PORT-г тохируулна; локал дээр 5001.
    # debug нь зөвхөн FLASK_DEBUG=1 үед асна (production-д унтраалттай байх ёстой).
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
