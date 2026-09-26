"""Бүтэц үүсгэх: init_db() — бүх SCHEMA_* + шинэчлэлт + timestamp (SQLite ба Postgres)."""

from core.db import IS_PG, get_db
from core.db.schema_base import SCHEMA, SCHEMA_UNION
from core.db.schema_admin import SCHEMA_CONTENT, SCHEMA_REF, SCHEMA_USER
from core.db.schema_portal import SCHEMA_FEEDBACK, SCHEMA_FORM, SCHEMA_NEWS, SCHEMA_NOTIFY
from core.db.schema_home import SCHEMA_HOME
from core.db.migrate import _ensure_timestamps, _migrate
from core.db.pg_schema import _pg_migrate, _pg_schema, _pg_timestamps


def init_db():
    conn = get_db()
    # Лавлахууд (SCHEMA_REF) нь union/user-ийн FK-ийн бай тул ЭХЭЛЖ үүснэ.
    scripts = [SCHEMA, SCHEMA_REF, SCHEMA_UNION, SCHEMA_USER, SCHEMA_CONTENT,
               SCHEMA_NEWS, SCHEMA_FEEDBACK, SCHEMA_NOTIFY, SCHEMA_FORM, SCHEMA_HOME]
    if IS_PG:
        alters = []
        for sc in scripts:
            ddl, fks = _pg_schema(sc)
            conn.executescript(ddl)
            alters += fks
        for a in alters:
            conn.executescript(a)
        _pg_migrate(conn)            # хуучин PG DB-д дутуу багана нэмэх
        _pg_timestamps(conn)
    else:
        for sc in scripts:
            conn.executescript(sc)
        _migrate(conn)
        _ensure_timestamps(conn)     # бүх хүснэгтэд created_at/updated_at + trigger
    conn.commit()
    conn.close()
