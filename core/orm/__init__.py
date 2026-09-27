"""SQLAlchemy 2.0 — engine, session ба model-ууд.

    from core.orm import session
    from core.orm.models import Member
    s = session()                                   # хүсэлтийн session (Flask g)
    s.scalars(select(Member).where(Member.organization_id == 5)).all()

* SQLite (DATABASE_URL өгөөгүй) эсвэл Postgres (DATABASE_URL) — core.db-ийн шилжүүлэгч.
  SQLite-ийн замыг (`core.db.DB_PATH`) engine үүсгэх агшинд уншдаг тул тест сольж болно.
* Процесс (pid) тутамд нэг engine: gunicorn --preload мастер ensure_seeded()-ийн дараа
  `dispose()` дуудаж сокетоо fork-д өвлүүлэхгүй; ажилтан бүр өөрийн pool-оо барина.
  Postgres: pool_size DB_POOL_MAX (анхдагч 5), pool_pre_ping — RDS дахин асвал үхсэн
  холболтыг солино. SQLite: холболт бүрд PRAGMA foreign_keys=ON (каскад үүнээс хамаарна).
* Хүсэлт бүр НЭГ session (Flask g); teardown нь rollback + close хийнэ — commit хийгээгүй
  өөрчлөлт хэзээ ч алдаанаас хойш үлдэхгүй, холболт pool руу буцна.
"""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from core import db as _db
from core.orm.base import Base  # noqa: F401  (models импортлоход хэрэгтэй)

_engines = {}


def _url():
    if _db.IS_PG:
        url = _db.DATABASE_URL
        for old in ("postgresql://", "postgres://"):
            if url.startswith(old):
                return "postgresql+psycopg://" + url[len(old):]
        return url
    return f"sqlite:///{_db.DB_PATH}"


def engine():
    """Энэ процессын engine (URL өөрчлөгдвөл — тестэд — шинээр үүснэ)."""
    key = (os.getpid(), _url())
    eng = _engines.get(key)
    if eng is None:
        if _db.IS_PG:
            eng = create_engine(key[1], pool_size=int(os.environ.get("DB_POOL_MAX", "5")),
                                max_overflow=0, pool_pre_ping=True, pool_timeout=15)
        else:
            eng = create_engine(key[1])

            @event.listens_for(eng, "connect")
            def _fk_on(dbapi_conn, _record):
                dbapi_conn.execute("PRAGMA foreign_keys = ON")
        _engines[key] = eng
    return eng


def new_session():
    """Хүсэлтээс гадуурх (скрипт, seed) session — дуудагч өөрөө close() хийнэ."""
    return Session(engine(), expire_on_commit=True)


def session():
    """Хүсэлтийн session — Flask g-д нэг л удаа үүсгэнэ; хүсэлтээс гадуур бол шинэ."""
    from flask import g, has_app_context
    if not has_app_context():
        return new_session()
    if "orm_session" not in g:
        g.orm_session = new_session()
    return g.orm_session


def close_request_session(_exc=None):
    """teardown_appcontext: commit хийгээгүйг rollback, холболтыг pool руу буцаана."""
    from flask import g
    s = g.pop("orm_session", None)
    if s is not None:
        s.close()


def dispose():
    """Энэ процессын engine-ийг хаана (--preload мастер fork-оос өмнө, скрипт дуусахад)."""
    for key in [k for k in _engines if k[0] == os.getpid()]:
        _engines.pop(key).dispose()
