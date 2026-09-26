"""core/audit.py — хүсэлт бүрийн JSON лог (stdout -> CloudWatch)."""
import json
import logging

import pytest

from conftest import uniq


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(json.loads(record.getMessage()))


@pytest.fixture
def audit_lines():
    h = _Collect()
    logger = logging.getLogger("edu_union.audit")
    logger.addHandler(h)
    yield h.lines
    logger.removeHandler(h)


def test_request_line_has_user_and_status(api, audit_lines):
    api.get("/api/role?x=1")
    rec = next(r for r in audit_lines if r["event"] == "request" and r["path"] == "/api/role")
    assert rec["method"] == "GET" and rec["status"] == 200
    assert rec["username"] == "admin" and rec["user_id"] == 1
    assert rec["query"] == "x=1"
    assert isinstance(rec["ms"], float) and rec["ts"].endswith("+00:00")


def test_anonymous_and_rejected_requests_logged(anon, audit_lines):
    anon.get("/api/member", headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    rec = next(r for r in audit_lines if r.get("path") == "/api/member")
    assert rec["status"] == 401 and rec["user_id"] is None
    assert rec["ip"] == "203.0.113.9"                    # nginx-ийн X-Forwarded-For


def test_login_events_never_contain_password(client, audit_lines):
    pw = uniq("NotLogged")
    client.post("/api/login", json={"username": "admin", "password": pw})
    client.post("/api/login", json={"username": "admin", "password": "admin123"})
    events = [r for r in audit_lines if r["event"] in ("login", "login_failed")]
    assert [e["event"] for e in events] == ["login_failed", "login"]
    assert events[0]["username"] == "admin" and events[0]["reason"] == "bad_credentials"
    assert events[1]["user_id"] == 1
    assert all(pw not in json.dumps(r, ensure_ascii=False) for r in audit_lines)


def test_healthcheck_and_preflight_skipped(anon, audit_lines):
    anon.get("/api/portal/forms", headers={"User-Agent": "Python-urllib/3.12"})
    anon.request("OPTIONS", "/api/member")
    assert not [r for r in audit_lines if r.get("path") in ("/api/portal/forms", "/api/member")]
    anon.get("/api/portal/forms", headers={"User-Agent": "Mozilla/5.0"})
    assert [r for r in audit_lines if r.get("path") == "/api/portal/forms"]
