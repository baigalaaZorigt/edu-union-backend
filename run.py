"""Оруулах цэг — Flask апп үүсгэж, хоёр site-ийн blueprint-уудыг холбоно.

    python run.py                 # dev сервер (default порт 5001)
    FLASK_DEBUG=1 python run.py   # auto-reload/debug-тэй dev сервер
    gunicorn run:app              # production (Render г.м.) — `app` объектыг ачаална

Порт нь PORT орчны хувьсагчаас (Render/Heroku тохируулна), эс бөгөөс 5001.

Бүтэц:
  client/  — үйлчлүүлэгчийн site (засаг захиргаа + үйлдвэрчний эвлэлийн өгөгдөл)
  admin/   — удирдлагын site (хэрэглэгч / эрх / дүр)
  db.py, helpers.py — хоёр site-ийн хуваалцсан суурь (DB, туслахууд)
"""
import os

from flask import Flask

from db import ensure_seeded
from helpers import register_error_handlers

# --- client site ---
from client.admin_units import bp as admin_units_bp
from client.union import bp as union_bp

# --- admin site ---
from admin.users import bp as users_bp


def create_app():
    """Flask апп үүсгэж, тохиргоо ба blueprint-уудыг холбоно."""
    app = Flask(__name__)
    app.json.ensure_ascii = False  # Кирилл үсгийг escape хийлгүй буцаах

    # Client site — засаг захиргаа + үйлдвэрчний эвлэл
    app.register_blueprint(admin_units_bp)
    app.register_blueprint(union_bp)

    # Admin site — хэрэглэгчийн удирдлага
    app.register_blueprint(users_bp)

    register_error_handlers(app)  # 400/404/409 -> {"error": ...} JSON (бүх blueprint-д)
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
