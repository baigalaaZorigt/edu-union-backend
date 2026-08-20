"""Нэвтрэлт ба эрхийн хяналт (authentication + authorization).

Загвар — JWT токенд суурилсан:
  1. `/api/login` нь JWT токен (PyJWT, HS256) буцаана.
  2. Дараагийн хүсэлт бүр `Authorization: Bearer <jwt>` толгойгоор ирнэ.
  3. `require_auth()` (app.before_request) токен шалгаад, зам + HTTP методоос
     шаардагдах эрхийг (resource.action) гарган хэрэглэгчийн эрхтэй тулгана.

Ингэснээр endpoint бүрд гараар decorator тавихгүйгээр бүх API эрхээс хамаарна.
JWT нь итгэмжлэлгүй (stateless) — SECRET_KEY-ээр HS256-аар гарын үсэг зурж, exp-тэй.
Production-д SECRET_KEY орчны хувьсагчийг заавал тохируулна уу.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT
from flask import request, abort, g
from werkzeug.exceptions import HTTPException

from db import get_db

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-CHANGE-IN-PRODUCTION")
JWT_ALGORITHM = "HS256"
TOKEN_MAX_AGE = 60 * 60 * 12  # 12 цаг хүчинтэй

# HTTP метод -> эрхийн үйлдэл (action)
METHOD_ACTION = {
    "GET": "read", "HEAD": "read",
    "POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete",
}

# URL замын эхний хэсэг -> эрхийн resource. Энд байхгүй бол хэсгийн нэрийг шууд авна.
PATH_RESOURCE = {
    "au1": "admin_unit", "au2": "admin_unit", "au3": "admin_unit",
    # Судалгаа/санал асуулга — спекийн олон тоот URL -> хүснэгтийн нэр
    "forms": "form", "questions": "form_question", "options": "form_option",
    "documents": "form_document",
}

# /api/<site>/... хэлбэрийн site угтварууд — эрхийг ДАРААГИЙН хэсгээс гаргана
# (ж: /api/admin/forms -> form, /api/portal/forms -> form).
SITE_PREFIXES = ("admin", "portal")

# Дэд зам нь өөрийн resource-тэй үед (ж: /api/admin/forms/5/questions -> form_question).
# Хамгийн сүүлд таарсан нь ялна: .../questions/9/answers -> form_result.
SUB_RESOURCE = {
    "questions": "form_question",
    "options": "form_option",
    "document": "form_document", "documents": "form_document",
    "results": "form_result", "answers": "form_result",
    "submit": "form_submission", "submissions": "form_submission",
}

# HTTP методоос гарах үйлдлийг дарж бичих дэд замууд
# (ж: POST .../publish бол шинээр үүсгэх биш, төлөв ЗАСАХ үйлдэл).
SUB_ACTION = {"publish": "update", "close": "update", "reorder": "update"}

# Токен шаардахгүй нээлттэй замууд (нэвтрэлт)
PUBLIC_PATHS = {"/api/login"}

# Токен шаардахгүй нээлттэй угтваруудтай замууд.
# /uploads/     — порталын <img src>/татах холбоос толгой дамжуулж чаддаггүй тул
#                 байршуулсан зураг/файлыг нээлттэй үйлчилнэ (оруулах нь /api/upload —
#                 хамгаалалттай).
# /api/portal/  — порталын судалгаа / санал асуулга БҮХЭЛДЭЭ нээлттэй: зочин
#                 нэвтрэхгүйгээр жагсаалтыг хараад бөглөж чадна. Токен ирвэл
#                 _optional_user() түүнийг ачаалж, бөглөлтийг нэр дээр нь бүртгэнэ.
PUBLIC_PREFIXES = ("/uploads/", "/api/portal/")


def make_token(user_id):
    """Хэрэглэгчийн id-г агуулсан JWT токен үүсгэнэ (sub, iat, exp claim-тэй)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),                                  # subject — хэрэглэгчийн id
        "iat": now,                                           # үүсгэсэн хугацаа
        "exp": now + timedelta(seconds=TOKEN_MAX_AGE),        # дуусах хугацаа
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def _load_user(token):
    """JWT-г шалгаж, идэвхтэй хэрэглэгчийн мөрийг буцаана (эс бөгөөс 401)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        abort(401, description="Токены хугацаа дууссан — дахин нэвтэрнэ үү")
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        abort(401, description="Токен буруу байна")
    conn = get_db()
    row = conn.execute("SELECT * FROM app_user WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not row or not row["is_active"]:
        abort(401, description="Хэрэглэгч олдсонгүй эсвэл идэвхгүй байна")
    return row


def _user_permission_codes(user_row):
    """Хэрэглэгчийн дүрээс удамшсан бүх эрхийн код (set)."""
    if not user_row["role_id"]:
        return set()
    conn = get_db()
    codes = conn.execute(
        "SELECT p.code FROM role_permission rp "
        "JOIN permission p ON p.id = rp.permission_id WHERE rp.role_id=?",
        (user_row["role_id"],)).fetchall()
    conn.close()
    return {r["code"] for r in codes}


def _required_permission():
    """Одоогийн хүсэлтэд шаардагдах эрхийн код (resource.action) буцаана."""
    parts = request.path.strip("/").split("/")   # ж: ["api", "organization", "5"]
    if len(parts) < 2 or parts[0] != "api":
        return None
    action = METHOD_ACTION.get(request.method)
    if not action:
        return None
    parts = parts[1:]
    if parts[0] in SITE_PREFIXES and len(parts) > 1:   # /api/admin/... , /api/portal/...
        parts = parts[1:]
    resource = PATH_RESOURCE.get(parts[0], parts[0])
    for seg in parts[1:]:                # дэд зам resource/action-г дарж бичнэ
        if seg in SUB_RESOURCE:
            resource = SUB_RESOURCE[seg]
        if seg in SUB_ACTION:
            action = SUB_ACTION[seg]
    return f"{resource}.{action}"


def _optional_user():
    """Нээлттэй зам дээр токен ИРСЭН бол g.user-т ачаална (алдаа шидэхгүй).

    Портал нээлттэй ч, нэвтэрсэн хэрэглэгчийн бөглөлтийг түүний нэр дээр бүртгэж,
    `one_response` дүрмийг мөрдүүлэхийн тулд хэн болохыг мэдэх хэрэгтэй. Токен
    буруу/хугацаа дууссан бол ЗОЧИН гэж үзнэ — нээлттэй зам хаагдах ёсгүй.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return
    try:
        g.user = _load_user(header[len("Bearer "):].strip())
    except HTTPException:
        pass


def require_auth():
    """before_request хамгаалалт — нэвтрэлт (401) ба эрх (403)-ийг шалгана."""
    if request.method == "OPTIONS":          # CORS preflight
        return
    if request.path in PUBLIC_PATHS:         # нэвтрэлт нээлттэй
        return
    if request.path.startswith(PUBLIC_PREFIXES):   # нээлттэй зам (файл, портал)
        _optional_user()                           # токен ирсэн бол хэн болохыг тэмдэглэнэ
        return

    # 1) Нэвтрэлт — Bearer токен
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        abort(401, description="Нэвтрэх шаардлагатай (Authorization: Bearer <token>)")
    g.user = _load_user(header[len("Bearer "):].strip())

    # 2) Эрх — зам+методоос гарган тулгах
    need = _required_permission()
    if need and need not in _user_permission_codes(g.user):
        abort(403, description=f"Танд энэ үйлдлийн эрх алга: {need}")
