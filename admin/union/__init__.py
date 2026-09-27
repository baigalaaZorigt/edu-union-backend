"""Үйлдвэрчний эвлэлийн бүтцийн CRUD (Blueprint).

Түвшин: holboo (Холбоо) -> horoo (Хороо) -> organization (Гишүүн байгууллага) -> member (Гишүүн)
Нэмэлт: contact (Холбоо барих) — хороо/байгууллага/гишүүнд полиморфоор харьяалагдана
(нэг эзэмшигч ОЛОН утас/факс/и-мэйлтэй байж болно).

Байгууллага ба гишүүний маршрутууд нь хэрэглэгчийн ХАМРАХ ХҮРЭЭГЭЭР
(`scope_core`) автоматаар шүүгдэнэ — frontend тусдаа шүүлтүүр дамжуулах
шаардлагагүй (specialist_onboarding_api_spec.md §5). Хамрах хүрээний мөр
байхгүй хэрэглэгч (admin г.м.) бүгдийг хэвээр харна.

Модулиуд (бүгд НЭГ `union` blueprint дээр маршрутаа бүртгэнэ):
    common            — хуваалцсан тогтмол, SELECT, туслах функцууд
    horoo             — /api/horoo
    organization      — /api/organization
    member            — /api/member
    contact           — /api/contact
    salary            — /api/salary_request, /api/salary_scale
    references        — /api/education_degree|position|profession|reward_type|structure
    member_education  — /api/member_education
    member_reward     — /api/member_reward
    member_file       — /api/member_file (PDF хавсралт)
    export            — /api/member/export, /api/organization/export (Excel)
"""
from flask import Blueprint

bp = Blueprint("union", __name__)

# Маршрутын модулиудыг bp үүссэний ДАРАА импортлоно — тэд `bp`-г эндээс авна.
from admin.union import (  # noqa: E402,F401
    horoo, organization, member, contact, salary, references,
    member_education, member_reward, member_file, export,
)
