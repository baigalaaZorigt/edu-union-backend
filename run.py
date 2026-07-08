"""Оруулах цэг — Flask апп үүсгэж, хоёр site-ийн blueprint-уудыг холбоно.

    python run.py        # dev сервер http://127.0.0.1:5001 (debug=True)

Бүтэц:
  client/  — үйлчлүүлэгчийн site (засаг захиргаа + үйлдвэрчний эвлэлийн өгөгдөл)
  admin/   — удирдлагын site (хэрэглэгч / эрх / дүр)
  db.py, helpers.py — хоёр site-ийн хуваалцсан суурь (DB, туслахууд)
"""
from flask import Flask

from db import init_db
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
    init_db()                     # схем үргэлж бэлэн байлгана (өгөгдөл seed хийхгүй)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5001)
