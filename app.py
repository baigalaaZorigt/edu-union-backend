"""Нийцтэй байдлын оруулах цэг (compatibility shim).

Жинхэнэ апп нь `run.py` дотор (`create_app()`). Энэ файл нь зөвхөн хуучин
`python app.py` эхлүүлэх командыг (ж: Render-ийн default Start Command) ажиллуулах
зорилготой — `run.py` дэх `app` объектыг импортолж, dev серверийг асаана.

Production-д илүү найдвартай сонголт бол:  gunicorn run:app --bind 0.0.0.0:$PORT
"""
import os

from run import app  # noqa: F401  (create_app() импортлох үед ажиллаж, init_db хийнэ)

if __name__ == "__main__":
    # Render/Heroku PORT-г тохируулна; локал дээр 5001.
    # debug зөвхөн FLASK_DEBUG=1 үед (production-д унтраалттай).
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
