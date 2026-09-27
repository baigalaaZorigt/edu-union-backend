"""Хэрэглэгчийн удирдлагын CRUD (Blueprint).

Бүтэц:
  permission (Эрх)  — CRUD үйлдэл бүр нэг эрх (ж: 'user.create')
  role (Дүр)        — role_permission-оор дамжуулан ОЛОН эрхтэй (M:N)
  app_user (Хэрэглэгч) — role_id-аар нэг дүр СОНГОЖ, дүрийнхээ бүх эрхийг удамшуулна
  user_scope (Хамрах хүрээ) — тухайн хэрэглэгч АЛЬ өгөгдлийг харахыг заана (1:1)

Мөн "өөрийн" (self-service) маршрутууд — /api/change_password, /api/me/...
(specialist_onboarding_api_spec.md): анх нэвтрэхэд нууц үг солих, дараа нь
хамрах хүрээгээ баталгаажуулж onboarding-оо дуусгах. Эдгээр нь ҮРГЭЛЖ g.user
дээр ажиллах тул auth.py тусгай эрх шаардахгүй (SELF_PATHS / SELF_PREFIXES).

Модулиуд (бүгд НЭГ `users` blueprint дээр маршрутаа бүртгэнэ):
    common       — хуваалцсан тогтмол, user_select, туслах функцууд (public_user г.м.)
    permissions  — /api/permission
    roles        — /api/role, /api/role/<id>/permission
    accounts     — /api/user
    scope        — /api/user/<id>/scope
    me           — /api/login, /api/change_password, /api/me/...
"""
from flask import Blueprint

bp = Blueprint("users", __name__)

# Маршрутын модулиудыг bp үүссэний ДАРАА импортлоно — тэд `bp`-г эндээс авна.
from admin.users import permissions, roles, accounts, scope, me  # noqa: E402,F401
