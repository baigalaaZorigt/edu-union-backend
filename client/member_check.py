"""Гишүүний мэдээлэл шалгах (member-check-spec.md) — нэвтрэхгүйгээр, токенгүй.

    POST /api/member_check  {first_name, birth_date}
        -> 200 {exists, members: [{organization_name, last_name, first_name, position_name}]}

Нэр + төрсөн огноо таавал ажлын газар, албан тушаал ил болох тул:
  * Хариунд ЗӨВХӨН дээрх 4 талбар. `member_row()`-г ашиглахгүй — id, регистр г.м. гарах ёсгүй.
  * IP тутамд PER_MINUTE / PER_DAY хүсэлт -> 429. Тоолуур нь DB-д (`member_check_attempt`) —
    бүх gunicorn ажилтан хуваалцаж, restart-д тэглэгдэхгүй. Хуучирсан мөрийг ФИЗИКЭЭР
    цэвэрлэнэ: энэ нь бизнес өгөгдөл биш, IP-ийн богино хугацааны тоолуур.
  * Их бие лог-д бичигдэхгүй (core/audit.py их бие бичдэггүй); зөвхөн JSON биеэс уншина,
    query string нь лог-д бичигддэг тул.
"""
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import delete, func, select

from core.helpers import client_ip, now_str
from core.orm import session
from core.orm.ci import ci_lower
from core.orm.models import Member, MemberCheckAttempt, Organization, Position

bp = Blueprint("portal_member_check", __name__)

ACTIVE_STATUS = "идэвхтэй"
PER_MINUTE, PER_DAY = 10, 50
BLOCKED = "Хэт олон удаа шалгалаа — түр хүлээгээд дахин оролдоно уу"
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _caller_ip():
    """Rate limit-ийн IP. Next.js proxy-оор ирсэн бол X-Forwarded-For-ийн эхний утга.

    Бүх дуудлага Next.js (Vercel, тогтмол IP-гүй) -ээр ирдэг тул холболтын IP бүгдэд ижил; proxy-г
    IP-ээр таних боломжгүй тул MEMBER_CHECK_PROXY_SECRET-ийн утгатай X-Proxy-Secret толгойгоор
    таньна. Нууц таарахгүй бол X-Forwarded-For-т итгэхгүй — клиент түүнийг хуурамчаар тавьж чадна.
    """
    secret = os.environ.get("MEMBER_CHECK_PROXY_SECRET", "")
    sent = request.headers.get("X-Proxy-Secret", "")
    if secret and hmac.compare_digest(secret.encode(), sent.encode()):
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return client_ip()


def _ago(**delta):
    return (datetime.now(timezone.utc) - timedelta(**delta)).strftime("%Y-%m-%d %H:%M:%S")


def _rate_limit():
    """Хязгаар хэтэрсэн бол 429 (татгалзсан хүсэлт тоологдохгүй), эс бөгөөс нэгийг тоолно."""
    s = session()
    ip, day_ago = _caller_ip(), _ago(days=1)
    s.execute(delete(MemberCheckAttempt).where(MemberCheckAttempt.created_at < day_ago)
              .execution_options(hard=True))

    def count(cutoff):
        return s.scalar(select(func.count()).select_from(MemberCheckAttempt).where(
            MemberCheckAttempt.ip == ip, MemberCheckAttempt.created_at >= cutoff))
    blocked = count(_ago(minutes=1)) >= PER_MINUTE or count(day_ago) >= PER_DAY
    if not blocked:
        s.add(MemberCheckAttempt(ip=ip, created_at=now_str()))
    s.commit()
    if blocked:
        abort(429, description=BLOCKED)


def _validated():
    """(first_name, birth_date) эсвэл 400. strptime "1990-5-12"-г зөвшөөрдөг тул хэлбэрийг тусад нь."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="JSON их бие шаардлагатай")
    first_name, birth_date = data.get("first_name"), data.get("birth_date")
    # NUL тэмдэгтийг Postgres хүлээж авахгүй (500 болно)
    if not isinstance(first_name, str) or not first_name.strip() or "\x00" in first_name:
        abort(400, description="Нэр заавал бөглөнө")
    try:
        if not isinstance(birth_date, str) or not _DATE.fullmatch(birth_date):
            raise ValueError
        datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError:
        abort(400, description="Төрсөн огноо буруу байна (YYYY-MM-DD)")
    return first_name.strip(), birth_date


@bp.route("/api/member_check", methods=["POST"])
def member_check():
    _rate_limit()
    first_name, birth_date = _validated()
    rows = session().execute(
        select(Organization.name.label("organization_name"), Member.last_name, Member.first_name,
               Position.name.label("position_name"))
        .select_from(Member)
        .outerjoin(Organization, Organization.id == Member.organization_id)
        .outerjoin(Position, Position.id == Member.position_id)
        .where(Member.birth_date == birth_date,
               Member.member_status == ACTIVE_STATUS,
               ci_lower(func.trim(Member.first_name)) == first_name.lower())
        .order_by(Member.id)).mappings().all()
    return jsonify(exists=bool(rows), members=[dict(r) for r in rows])
