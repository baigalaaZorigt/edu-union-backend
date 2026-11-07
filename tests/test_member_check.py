"""POST /api/member_check — токенгүй гишүүн шалгах (member-check-spec.md)."""
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from _union_helpers import make_member, make_org
from conftest import uniq
from core.orm import new_session
from core.orm.models import MemberCheckAttempt

URL = "/api/member_check"
DATE = "1984-03-27"
_ip_counter = [0]


def fresh_ip():
    """Тест бүр өөрийн IP-тэй — rate limit бие биедээ нөлөөлөхгүй."""
    _ip_counter[0] += 1
    return f"198.51.{_ip_counter[0] // 250}.{_ip_counter[0] % 250 + 1}"


def check(anon, first_name, birth_date=DATE, ip=None, headers=None):
    h = {"X-Real-IP": ip or fresh_ip(), **(headers or {})}
    return anon.post(URL, json={"first_name": first_name, "birth_date": birth_date}, headers=h)


def active(api, org_id, **extra):
    return make_member(api, org_id, birth_date=DATE, member_status="идэвхтэй", **extra)


def test_found_returns_only_the_four_public_fields(api, anon):
    pos = api.post("/api/position", json={"code": uniq("p"), "name": uniq("Багш ")}).get_json()
    org = make_org(api)
    name = uniq("Сараа")
    active(api, org["id"], first_name=name, last_name="Болд", position_id=pos["id"],
           register_number="АА90051212", email="x@example.mn")
    r = check(anon, name)
    assert r.status_code == 200
    assert r.get_json() == {"exists": True, "members": [{
        "organization_name": org["name"], "last_name": "Болд",
        "first_name": name, "position_name": pos["name"]}]}


def test_not_found_is_200(anon):
    r = check(anon, uniq("Байхгүй"))
    assert r.status_code == 200 and r.get_json() == {"exists": False, "members": []}


def test_position_is_optional(api, anon):
    name = uniq("Туяа")
    active(api, make_org(api)["id"], first_name=name)
    assert check(anon, name).get_json()["members"][0]["position_name"] is None


def test_name_is_trimmed_and_case_insensitive_in_cyrillic_returned_as_stored(api, anon):
    name = uniq("Өлзий")
    active(api, make_org(api)["id"], first_name=name)
    for typed in (f"  {name}  ", name.upper(), name.lower()):
        assert check(anon, typed).get_json()["members"][0]["first_name"] == name


def test_exact_match_only_no_partial_no_wildcard(api, anon):
    name = uniq("Номин")
    active(api, make_org(api)["id"], first_name=name)
    for typed in (name[:-1], name + "а", "%", "Номин%", "_" * len(name)):
        assert check(anon, typed).get_json()["exists"] is False


def test_birth_date_must_match(api, anon):
    name = uniq("Ану")
    active(api, make_org(api)["id"], first_name=name)
    assert check(anon, name, "1984-03-28").get_json()["exists"] is False


def test_all_namesakes_across_organizations(api, anon):
    name = uniq("Болор")
    orgs = [make_org(api), make_org(api)]
    for o in orgs:
        active(api, o["id"], first_name=name)
    got = check(anon, name).get_json()["members"]
    assert [m["organization_name"] for m in got] == [o["name"] for o in orgs]


@pytest.mark.parametrize("status", ["идэвхгүй", None])
def test_only_active_members_count(api, anon, status):
    name = uniq("Заяа")
    extra = {"member_status": status} if status else {}
    make_member(api, make_org(api)["id"], first_name=name, birth_date=DATE, **extra)
    assert check(anon, name).get_json()["exists"] is False


def test_deleted_member_is_not_found(api, anon):
    name = uniq("Солонго")
    m = active(api, make_org(api)["id"], first_name=name)
    assert check(anon, name).get_json()["exists"] is True
    assert api.delete(f"/api/member/{m['id']}").status_code == 200
    assert check(anon, name).get_json()["exists"] is False


@pytest.mark.parametrize("body", [
    {"birth_date": DATE}, {"first_name": "   ", "birth_date": DATE},
    {"first_name": 5, "birth_date": DATE}, {"first_name": "A\x00", "birth_date": DATE},
    {"first_name": "Сараа"}, {"first_name": "Сараа", "birth_date": "1990-02-30"},
    {"first_name": "Сараа", "birth_date": "1990-5-12"},
    {"first_name": "Сараа", "birth_date": "12/05/1990"},
    {"first_name": "Сараа", "birth_date": 19900512}, [1], None,
])
def test_invalid_body_is_400(anon, body):
    r = anon.post(URL, json=body, headers={"X-Real-IP": fresh_ip()})
    assert r.status_code == 400 and r.get_json()["error"]


def test_minute_limit_429_per_ip(anon):
    ip = fresh_ip()
    for _ in range(10):
        assert check(anon, "Хэн", ip=ip).status_code == 200
    r = check(anon, "Хэн", ip=ip)
    assert r.status_code == 429 and r.get_json()["error"]
    assert check(anon, "Хэн").status_code == 200                    # өөр IP хаагдаагүй


def test_bad_requests_count_too(anon):
    ip = fresh_ip()
    for _ in range(10):
        anon.post(URL, json={}, headers={"X-Real-IP": ip})
    assert check(anon, "Хэн", ip=ip).status_code == 429


def _age_attempts(ip, created_at):
    s = new_session()
    s.execute(update(MemberCheckAttempt).where(MemberCheckAttempt.ip == ip)
              .values(created_at=created_at))
    s.commit()
    s.close()


def test_day_limit_and_expired_rows_are_purged(anon):
    ip = fresh_ip()
    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    for _ in range(5):
        for _ in range(10):
            assert check(anon, "Хэн", ip=ip).status_code == 200
        _age_attempts(ip, hour_ago)             # минутын цонхноос гарна, өдрийнхөд хэвээр
    assert check(anon, "Хэн", ip=ip).status_code == 429

    _age_attempts(ip, "2000-01-01 00:00:00")    # 24 цагаас хуучирсан -> цэвэрлэгдээд дахин нээлттэй
    assert check(anon, "Хэн", ip=ip).status_code == 200
    s = new_session(include_deleted=True)
    rows = s.scalars(select(MemberCheckAttempt).where(MemberCheckAttempt.ip == ip)).all()
    s.close()
    assert len(rows) == 1


def test_forwarded_ip_trusted_only_with_proxy_secret(anon, monkeypatch):
    monkeypatch.setenv("MEMBER_CHECK_PROXY_SECRET", "s3cret")
    conn_ip, client_a, client_b = fresh_ip(), fresh_ip(), fresh_ip()
    good = {"X-Proxy-Secret": "s3cret"}

    # Next.js-ээр: нэг холболтын IP ч хэрэглэгч бүр өөрийн тоолууртай (nginx сүүлд нь залгана)
    for _ in range(10):
        h = {**good, "X-Forwarded-For": f"{client_a}, {conn_ip}"}
        assert check(anon, "Хэн", ip=conn_ip, headers=h).status_code == 200
    h = {**good, "X-Forwarded-For": f"{client_a}, {conn_ip}"}
    assert check(anon, "Хэн", ip=conn_ip, headers=h).status_code == 429
    h = {**good, "X-Forwarded-For": f"{client_b}, {conn_ip}"}
    assert check(anon, "Хэн", ip=conn_ip, headers=h).status_code == 200

    # Гаднаас: хуурамч X-Forwarded-For (нууцгүй / буруу нууц) хязгаарыг тойрохгүй
    spoofer = fresh_ip()
    for i in range(10):
        h = {"X-Forwarded-For": f"203.0.113.{i}, {spoofer}"}
        assert check(anon, "Хэн", ip=spoofer, headers=h).status_code == 200
    for bad in ({}, {"X-Proxy-Secret": "wrong"}, {"X-Proxy-Secret": "нууц"}):
        h = {**bad, "X-Forwarded-For": f"203.0.113.99, {spoofer}"}
        assert check(anon, "Хэн", ip=spoofer, headers=h).status_code == 429


def test_forwarded_ip_ignored_when_secret_not_configured(anon, monkeypatch):
    monkeypatch.delenv("MEMBER_CHECK_PROXY_SECRET", raising=False)
    ip = fresh_ip()
    for i in range(10):
        assert check(anon, "Хэн", ip=ip, headers={"X-Forwarded-For": f"203.0.113.{i}",
                                                  "X-Proxy-Secret": ""}).status_code == 200
    assert check(anon, "Хэн", ip=ip, headers={"X-Forwarded-For": "203.0.113.50",
                                              "X-Proxy-Secret": ""}).status_code == 429


def test_only_this_route_is_exempt_from_auth(anon, api):
    assert anon.get(URL).status_code == 405                         # POST л
    assert anon.post(f"{URL}/x", json={}).status_code == 401
    assert anon.get("/api/member").status_code == 401
    assert anon.post("/api/member", json={}).status_code == 401


def test_name_and_birth_date_never_logged(anon):
    lines = []

    class Collect(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())
    h = Collect()
    logger = logging.getLogger("edu_union.audit")
    logger.addHandler(h)
    try:
        name = uniq("НууцНэр")
        assert check(anon, name).status_code == 200
    finally:
        logger.removeHandler(h)
    assert any(URL in line for line in lines)
    assert not any(name in line or DATE in line for line in lines)
