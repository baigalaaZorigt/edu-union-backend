"""Хэрэглэгчийн үйлдлийн лог (audit) — JSON мөрөөр stdout руу.

Аппын сервер дээр лог ФАЙЛ бичихгүй: бүх лог stdout/stderr-ээр гарч, Docker-ийн
`awslogs` драйвер (deploy/setup-s3-cloudwatch.sh тохируулна) шууд CloudWatch Logs руу
илгээнэ. JSON тул CloudWatch Logs Insights-аар шүүнэ, ж:

    fields ts, user_id, method, path, status | filter event="request" and status>=400

Хүсэлт бүрд нэг мөр: хэн (user_id, username), юу (method, path, status), хаанаас (ip,
ua), хэр удсан (ms). Их бие (нууц үг г.м.) хэзээ ч бичигдэхгүй. Docker-ийн healthcheck-ийн
давтамжит хүсэлтийг алгасна. `event()` нь тусгай үйл явдал (нэвтрэлт г.м.) бичнэ.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from flask import g, request

log = logging.getLogger("edu_union.audit")

# Docker-ийн healthcheck (docker-compose.yml) — 30 сек тутам, логийг бохирдуулна
HEALTHCHECK = ("/api/portal/forms", "Python-urllib")


def _emit(record):
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record}
    log.info(json.dumps(record, ensure_ascii=False, default=str))


def _client_ip():
    # nginx X-Forwarded-For-ийг дамжуулдаг; эхнийх нь жинхэнэ клиент
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() or request.remote_addr


def _user():
    user = getattr(g, "user", None)
    if user is None:
        return None, None
    return user["id"], user["username"]


def event(name, **fields):
    """Тусгай үйл явдал (ж: login_failed) — хүсэлтийн мэдээлэлтэй хамт."""
    user_id, username = _user()
    _emit({"event": name, "user_id": user_id, "username": username,
           "ip": _client_ip(), **fields})


def _start():
    g._audit_t0 = time.perf_counter()


def _finish(response):
    if request.method == "OPTIONS":
        return response
    if request.path == HEALTHCHECK[0] and \
            request.headers.get("User-Agent", "").startswith(HEALTHCHECK[1]):
        return response
    user_id, username = _user()
    t0 = getattr(g, "_audit_t0", None)
    _emit({
        "event": "request",
        "method": request.method,
        "path": request.path,
        "query": request.query_string.decode("utf-8", "replace") or None,
        "status": response.status_code,
        "ms": round((time.perf_counter() - t0) * 1000, 1) if t0 else None,
        "user_id": user_id,
        "username": username,
        "ip": _client_ip(),
        "ua": request.headers.get("User-Agent"),
    })
    return response


def init_app(app):
    """stdout руу JSON мөр бичих logger + хүсэлт бүрийн before/after hook."""
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.propagate = False
    log.setLevel(os.environ.get("AUDIT_LOG_LEVEL", "INFO"))
    app.before_request(_start)       # require_auth-аас ӨМНӨ — 401/403-ийн хугацаа ч орно
    app.after_request(_finish)
