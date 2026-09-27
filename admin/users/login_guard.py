"""Нэвтрэх оролдлогын хязгаар (brute-force хамгаалалт) — /api/login ашиглана.

БУРУУ оролдлого бүрийг `login_attempt`-д бичнэ; WINDOW_MINUTES дотор:
  * (хэрэглэгчийн нэр + IP) хослолоор MAX_PER_USER_IP -> 429
  * IP-ээр нийт MAX_PER_IP                            -> 429 (олон нэрээр туршихад)
Зөвхөн нэрээр түгжихгүй — эс бөгөөс гадны хэн ч `admin`-ыг 5 буруу оролдлогоор түгжиж
чадна (lockout DoS). Амжилттай нэвтрэлт тухайн нэр+IP-ийн тоолуурыг тэглэнэ.
IP нь core.helpers.client_ip() (nginx-ийн X-Real-IP).
"""
from datetime import datetime, timedelta, timezone

from core import audit
from core.helpers import client_ip, fail, now_str

WINDOW_MINUTES = 15
MAX_PER_USER_IP = 5
MAX_PER_IP = 20
BLOCKED = f"Хэт олон удаа буруу оролдлоо — {WINDOW_MINUTES} минутын дараа дахин оролдоно уу"


def _cutoff():
    return (datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)) \
        .strftime("%Y-%m-%d %H:%M:%S")


def check(conn, username):
    """Хязгаар хэтэрсэн бол 429 (холболтыг хаана). Хуучирсан мөрүүдийг цэвэрлэнэ."""
    cutoff, ip = _cutoff(), client_ip()
    conn.execute("DELETE FROM login_attempt WHERE created_at < ?", (cutoff,))
    by_ip = conn.execute("SELECT COUNT(*) FROM login_attempt WHERE ip=? AND created_at >= ?",
                         (ip, cutoff)).fetchone()[0]
    by_pair = conn.execute("SELECT COUNT(*) FROM login_attempt WHERE ip=? AND username=? "
                           "AND created_at >= ?", (ip, username, cutoff)).fetchone()[0]
    conn.commit()
    if by_pair >= MAX_PER_USER_IP or by_ip >= MAX_PER_IP:
        audit.event("login_blocked", username=username,
                    reason="user_ip" if by_pair >= MAX_PER_USER_IP else "ip")
        fail(conn, 429, BLOCKED)


def record_failure(conn, username):
    conn.execute("INSERT INTO login_attempt(username, ip, created_at) VALUES (?, ?, ?)",
                 (username, client_ip(), now_str()))
    conn.commit()


def reset(conn, username):
    conn.execute("DELETE FROM login_attempt WHERE username=? AND ip=?", (username, client_ip()))
