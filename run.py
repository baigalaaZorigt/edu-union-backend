"""Оруулах цэг — Flask апп үүсгэж, хоёр site-ийн blueprint-уудыг холбоно.

    python run.py                 # dev сервер (default порт 5001)
    FLASK_DEBUG=1 python run.py   # auto-reload/debug-тэй dev сервер
    gunicorn run:app              # production (docker) — `app` объектыг ачаална

Порт нь PORT орчны хувьсагчаас, эс бөгөөс 5001.

Бүтэц:
  admin/   — admin панелийн API (токен + эрх): засаг захиргаа, ҮЭ-ийн өгөгдөл,
             хэрэглэгч/эрх/дүр, порталын цэс/контент, судалгаа, мэдээ, мэдэгдэл
  client/  — порталын нээлттэй API (токенгүй): /api/portal/..., /api/public/...
  core/    — хоёр site-ийн хуваалцсан суурь (DB, auth, туслахууд, *_core домэйн)
  scripts/ — гараар/cron-оор ажиллуулах скриптүүд
"""
import os

from flask import Flask, request

from core.db import ensure_seeded
from core.helpers import register_error_handlers
from core.auth import require_auth, SECRET_KEY

# --- admin site: токен + эрх шаардана (admin панел) ---
from admin.admin_units import bp as admin_units_bp
from admin.union import bp as union_bp
from admin.union.member_file import MAX_FILE_SIZE
from admin.users import bp as users_bp
from admin.content import bp as content_bp
from admin.forms import bp as admin_forms_bp
from admin.news import bp as admin_news_bp
from admin.settings import bp as portal_settings_bp
from admin.feedback import bp as admin_feedback_bp
from admin.notifications import bp as notifications_bp
from admin.dashboard import bp as admin_dashboard_bp
# --- client site: порталын нээлттэй (токенгүй) API ---
from client.forms import bp as portal_forms_bp
from client.news import bp as portal_news_bp
from client.feedback import bp as portal_feedback_bp
from client.settings import bp as public_settings_bp

# Бүртгэх blueprint-ууд. ШИНЭ blueprint-ийг энд нэмэхгүй бол түүний маршрут харагдахгүй.
BLUEPRINTS = (
    # Admin site — токен + эрх (admin панел)
    admin_units_bp,       # /api/au1|au2|au3, /api/school_category
    union_bp,             # /api/horoo|organization|member|contact|...
    users_bp,             # /api/permission|role|user, /api/login, /api/me
    content_bp,           # /api/menu|page|page_block|upload
    admin_forms_bp,       # /api/admin/... — судалгаа/санал асуулга
    admin_news_bp,        # /api/admin/news... — мэдээ, зар
    portal_settings_bp,   # /api/portal_settings — порталын тохиргоо
    admin_feedback_bp,    # /api/admin/suggestions|complaints
    notifications_bp,     # /api/admin/notifications + /api/notifications
    admin_dashboard_bp,   # /api/admin/dashboard/summary
    # Client site — портал, токенгүй (core/auth.py-ийн PUBLIC_PREFIXES)
    portal_forms_bp,      # /api/portal/forms... — судалгаа бөглөх
    portal_news_bp,       # /api/portal/news — мэдээ унших
    portal_feedback_bp,   # /api/portal/suggestions|complaints
    public_settings_bp,   # /api/public|portal/portal_settings
)


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
    # (admin/union/member_file.py), энэ нь олон файлыг нэг дор илгээх боломж үлдээж, сервер
    # рүү хэт том хүсэлт ирэхээс хамгаална (хэтэрвэл 413 -> {"error": ...}).
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE * 5

    # Нэвтрэлт + эрхийн хяналт: /api/login болон /api/portal/, /uploads/-аас бусад
    # бүх хүсэлтэд токен + эрх шаардана (core/auth.py-ийн PUBLIC_* -ыг үзнэ үү).
    app.before_request(require_auth)
    app.after_request(add_cors_headers)   # браузерын client өөр домэйнээс хандана

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    register_error_handlers(app)  # 400/401/403/404/405/409/413/422 -> {"error": ...} JSON
    ensure_seeded()               # схем + хоосон хүснэгтийг автоматаар seed хийнэ
    return app


app = create_app()


if __name__ == "__main__":
    # PORT орчны хувьсагч эсвэл 5001.
    # debug нь зөвхөн FLASK_DEBUG=1 үед асна (production-д унтраалттай байх ёстой).
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
