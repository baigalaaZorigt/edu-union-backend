"""pytest-ийн хуваалцсан fixture-ууд.

Тест бүр ТҮР SQLite DB дээр ажиллана (жинхэнэ `admin_units.db`-д хүрэхгүй):
`db.DB_PATH`-ийг `run`-ийг импортлохоос ӨМНӨ сольж, файл хадгалах сангуудыг
түр хавтас руу чиглүүлнэ. Схем + seed нэг удаа (session) үүснэ.

    .venv/bin/python -m pytest tests -q
"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP = tempfile.mkdtemp(prefix="edu-union-test-")
os.environ.pop("DATABASE_URL", None)                 # үргэлж SQLite
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "member")
os.environ["CONTENT_UPLOAD_DIR"] = os.path.join(_TMP, "content")
os.environ["FORM_UPLOAD_DIR"] = os.path.join(_TMP, "form")

from core import db  # noqa: E402

db.DB_PATH = os.path.join(_TMP, "test.db")

import run  # noqa: E402  (импортлоход create_app() + ensure_seeded() ажиллана)

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG_BYTES = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
             b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
             b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


class Api:
    """Flask test client-ийг Bearer токентой ороосон туслах."""

    def __init__(self, client, token=None):
        self.client = client
        self.token = token

    def _headers(self, headers):
        h = dict(headers or {})
        if self.token:
            h.setdefault("Authorization", f"Bearer {self.token}")
        return h

    def request(self, method, url, json=None, data=None, headers=None, **kw):
        return self.client.open(url, method=method, json=json, data=data,
                                headers=self._headers(headers), **kw)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, json=None, **kw):
        return self.request("POST", url, json=json, **kw)

    def put(self, url, json=None, **kw):
        return self.request("PUT", url, json=json, **kw)

    def patch(self, url, json=None, **kw):
        return self.request("PATCH", url, json=json, **kw)

    def delete(self, url, **kw):
        return self.request("DELETE", url, **kw)


@pytest.fixture(scope="session")
def app():
    run.app.config["TESTING"] = True
    return run.app


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["token"]


@pytest.fixture(scope="session")
def api(client, admin_token):
    """Admin эрхтэй (бүх эрх) клиент."""
    return Api(client, admin_token)


@pytest.fixture(scope="session")
def anon(client):
    """Токенгүй клиент (порталын нээлттэй endpoint-уудад)."""
    return Api(client)


_counter = [0]


def uniq(prefix="t"):
    """Давхцахгүй богино нэр/код үүсгэнэ."""
    _counter[0] += 1
    return f"{prefix}{os.getpid() % 1000}{_counter[0]}"


@pytest.fixture
def make_user(api, client):
    """Өгөгдсөн эрхүүдтэй шинэ дүр + хэрэглэгч үүсгээд токентой Api буцаана.

    make_user(["member.read"], role_name="Зөвлөх мэргэжилтэн") -> (Api, user_json)
    """
    def _make(perm_codes=(), role_name=None, password="Pass1234"):
        role_name = role_name or uniq("role")
        r = api.post("/api/role", json={"name": role_name})
        assert r.status_code == 201, r.get_json()
        rid = r.get_json()["id"]
        if perm_codes:
            perms = {p["code"]: p["id"] for p in api.get("/api/permission").get_json()}
            for code in perm_codes:
                rr = api.post(f"/api/role/{rid}/permission",
                              json={"permission_id": perms[code]})
                assert rr.status_code in (200, 201), rr.get_json()
        username = uniq("user")
        r = api.post("/api/user", json={"username": username, "password": password,
                                        "last_name": "Тест", "first_name": "Хэрэглэгч",
                                        "role_id": rid})
        assert r.status_code == 201, r.get_json()
        user = r.get_json()
        lr = client.post("/api/login", json={"username": username, "password": password})
        assert lr.status_code == 200, lr.get_json()
        return Api(client, lr.get_json()["token"]), user
    return _make


@pytest.fixture(autouse=True)
def _clear_login_attempts():
    """Нэвтрэлтийн brute-force тоолуурыг тест бүрийн өмнө тэглэнэ — тестүүд бие биедээ
    (нэг IP-ээс буруу оролдлого хуримтлуулж) нөлөөлөхгүй."""
    from sqlalchemy import delete
    from core.orm import new_session
    from core.orm.models import LoginAttempt
    s = new_session()
    s.execute(delete(LoginAttempt))
    s.commit()
    s.close()
