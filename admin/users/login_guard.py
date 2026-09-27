"""Нэвтрэх оролдлогын хязгаар (brute-force хамгаалалт) — /api/login ашиглана.

БУРУУ оролдлого бүрийг `login_attempt`-д бичнэ; WINDOW_MINUTES дотор:
  * (хэрэглэгчийн нэр + IP) хослолоор MAX_PER_USER_IP -> 429
  * IP-ээр нийт MAX_PER_IP                            -> 429 (олон нэрээр туршихад)
Зөвхөн нэрээр түгжихгүй — эс бөгөөс гадны хэн ч `admin`-ыг 5 буруу оролдлогоор түгжиж
чадна (lockout DoS). Амжилттай нэвтрэлт тухайн нэр+IP-ийн тоолуурыг тэглэнэ.
IP нь core.helpers.client_ip() (nginx-ийн X-Real-IP).
"""
from datetime import datetime, timedelta, timezone

from flask import abort
from sqlalchemy import delete, func, select

from core import audit
from core.helpers import client_ip, now_str
from core.orm import session
from core.orm.models import LoginAttempt

WINDOW_MINUTES = 15
MAX_PER_USER_IP = 5
MAX_PER_IP = 20
BLOCKED = f"Хэт олон удаа буруу оролдлоо — {WINDOW_MINUTES} минутын дараа дахин оролдоно уу"


def _cutoff():
    return (datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)) \
        .strftime("%Y-%m-%d %H:%M:%S")


def _count(*conds):
    return session().scalar(select(func.count()).select_from(LoginAttempt).where(*conds))


def check(username):
    """Хязгаар хэтэрсэн бол 429. Хуучирсан мөрүүдийг цэвэрлэнэ."""
    s = session()
    cutoff, ip = _cutoff(), client_ip()
    s.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    recent = (LoginAttempt.ip == ip, LoginAttempt.created_at >= cutoff)
    by_ip = _count(*recent)
    by_pair = _count(*recent, LoginAttempt.username == username)
    s.commit()
    if by_pair >= MAX_PER_USER_IP or by_ip >= MAX_PER_IP:
        audit.event("login_blocked", username=username,
                    reason="user_ip" if by_pair >= MAX_PER_USER_IP else "ip")
        abort(429, description=BLOCKED)


def record_failure(username):
    s = session()
    s.add(LoginAttempt(username=username, ip=client_ip(), created_at=now_str()))
    s.commit()


def reset(username):
    session().execute(delete(LoginAttempt).where(LoginAttempt.username == username,
                                                 LoginAttempt.ip == client_ip()))
