"""Мэдэгдэл — админы илгээх тал + хэрэглэгчийн өөрийн inbox (Blueprint).

notification_api_spec.md-ийн хоёр хэсгийг НЭГ модуль хангана (frontend-ийн 2 дэлгэц):
    /api/admin/notifications        — админ бичиж илгээх, жагсаалт, устгах (§3)
    /api/notifications              — толгойн 🔔 дуут дохио: өөрийн inbox (§4)

Бүтэц: `notifications` (нэг мэдэгдэл) -> `notification_recipients` (fan-out:
хамрах хэрэглэгч бүрт нэг мөр + `read_at`). Хоёр site-д хуваагдахгүй (хоёулаа
admin site-ийн хэрэглэгчид) тул тусад нь `*_core` модуль гаргаагүй.

Inbox нь эрхээс ХАМААРАХГҮЙ: `/api/notifications` нь auth.py-ийн SELF_PATHS /
SELF_PREFIXES дотор — токен шаардана ч `notification.read` эрх шаардахгүй,
учир нь зөвхөн g.user-ийн ӨӨРИЙН мөрүүдэд хүрдэг (admin тал нь эрхтэй хэвээр).

Хуваарьт (scheduled) мэдэгдэл: `dispatch_due()` нь `scheduled_at` хүрсэн
мэдэгдлүүдийг илгээнэ. Репод үйлчилгээний scheduler байхгүй тул үүнийг
  * `scripts/send_due_notifications.py` (cron/systemd timer дуудна), мөн
  * жагсаалт/inbox уншихад ЗАЛХУУ (lazy) — cron тохируулаагүй ч ажиллахын тулд
хоёр талаас дуудна. Fan-out нь INSERT OR IGNORE + UNIQUE тул хэд ч удаа
ажиллуулахад аюулгүй.

Модулиуд (бүгд НЭГ `notifications` blueprint дээр):
    common        — тогтмол, шалгалт, fan-out, dispatch_due
    admin_routes  — /api/admin/notifications
    inbox         — /api/notifications
"""
from flask import Blueprint

bp = Blueprint("notifications", __name__)

# Маршрутын модулиудыг bp үүссэний ДАРАА импортлоно — тэд `bp`-г эндээс авна.
from admin.notifications import admin_routes, inbox  # noqa: E402,F401
from admin.notifications.common import dispatch_due  # noqa: E402,F401  (scripts/ ашиглана)
