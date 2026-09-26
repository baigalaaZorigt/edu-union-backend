"""Өгөгдлийн сангийн холболт ба бүтэц (schema) үүсгэх, JSON өгөгдлийг ачаалах.

ХОЁР САНГ ДЭМЖИНЭ:
  * SQLite  — анхдагч (локал хөгжүүлэлт, `admin_units.db` файл).
  * Postgres — `DATABASE_URL` орчны хувьсагч өгөгдсөн үед (ж: AWS RDS).

Маршрутын кодыг бүхэлд нь дахин бичихгүйн тулд Postgres талд НИМГЭН БҮРХҮҮЛ
(_PgConn/_PgCursor) тавьсан: SQLite-ийн бичиглэлийг (`?` placeholder,
`INSERT OR IGNORE`, `printf`, `julianday`, `lastrowid`) гүйцэтгэх агшинд
Postgres-ийн бичиглэл рүү хөрвүүлнэ. Ингэснээр 500 гаруй асуулга хэвээрээ
ажиллана.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo-ийн үндэс
DB_PATH = os.path.join(BASE_DIR, "admin_units.db")

# Postgres руу шилжих цорын ганц шилжүүлэгч: DATABASE_URL байвал Postgres.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = bool(DATABASE_URL)


def get_db():
    """Мөр бүрийг dict шиг хандах боломжтой холболт буцаана (SQLite эсвэл Postgres)."""
    if IS_PG:
        import psycopg
        return _PgConn(psycopg.connect(DATABASE_URL))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # PG-д FK үргэлж хүчинтэй
    return conn


# Дэд модулиуд — `get_db`, `IS_PG`, `BASE_DIR` ҮҮССЭНИЙ дараа импортлоно (тэд эдгээрийг
# `core.db`-ээс авна). `DB_PATH`-г get_db() дуудах агшинд ЭНД уншдаг тул тест/скрипт
# `core.db.DB_PATH`-г сольж болно. Хуучин `core.db.<нэр>` хандалт бүгд хэвээр ажиллана.
from core.db.schema_base import SCHEMA, SCHEMA_UNION
from core.db.schema_admin import SCHEMA_CONTENT, SCHEMA_REF, SCHEMA_USER
from core.db.schema_portal import SCHEMA_FEEDBACK, SCHEMA_FORM, SCHEMA_NEWS, SCHEMA_NOTIFY
from core.db.schema_home import SCHEMA_HOME
from core.db.reference_data import (DEFAULT_ROLES, EDUCATION_DEGREES, PERMISSION_ACTIONS,
                                    PERMISSION_RESOURCES, POSITIONS, PROFESSIONS,
                                    REWARD_TYPES, SALARY_SCALE, SCHOOL_CATEGORIES, STRUCTURES,
                                    STRUCTURE_CODES)
from core.db.pg import (Row, _PgConn, _PgCursor, _RE_INSERT, _RE_JULIAN, _RE_PRINTF,
                        _pg_row_factory, _to_pg)
from core.db.migrate_data import (SCHEMA_VERSION, _DROP_COLUMNS, _MIGRATIONS, _RENAME_COLUMNS,
                                  _SCHOOL_TYPE_MAP, _cols, _fill_ref_codes, _lookup_id,
                                  _migrate_data, _recompute_card_numbers,
                                  _shift_school_category_ids)
from core.db.migrate import (_ORG_COLUMNS, _TS_NOW, _TS_SKIP, _drop_org_horoo,
                             _ensure_timestamps, _migrate, _relax_submission_user)
from core.db.pg_schema import (pg_sync_sequences, _PG_TS_FN, _RE_FK, _RE_ID_PK, _RE_TABLE,
                               _pg_migrate, _pg_schema, _pg_tables, _pg_timestamps,
                               _split_statements, _strip_dangling_comma)
from core.db.schema import init_db
from core.db.seed_ref import (REFERENCE_SEEDS, seed_education_degree, seed_position,
                              seed_profession, seed_references, seed_reward_type,
                              seed_salary_scale, seed_school_category, seed_structure,
                              _seed_coded_ref, _seed_reference, _utc_now_iso)
from core.db.seed_portal import (DEFAULT_MENUS, DEFAULT_PORTAL_SETTINGS, seed_menu,
                                 seed_portal_settings, seed_users)
from core.db.seed_data import seed, seed_union, _load_json
from core.db.bootstrap import ensure_seeded, seed_all

__all__ = [
    "BASE_DIR",
    "DB_PATH",
    "DATABASE_URL",
    "IS_PG",
    "get_db",
    "SCHEMA",
    "SCHEMA_UNION",
    "SCHEMA_CONTENT",
    "SCHEMA_REF",
    "SCHEMA_USER",
    "SCHEMA_FEEDBACK",
    "SCHEMA_FORM",
    "SCHEMA_NEWS",
    "SCHEMA_NOTIFY",
    "SCHEMA_HOME",
    "DEFAULT_ROLES",
    "EDUCATION_DEGREES",
    "PERMISSION_ACTIONS",
    "PERMISSION_RESOURCES",
    "POSITIONS",
    "PROFESSIONS",
    "REWARD_TYPES",
    "SALARY_SCALE",
    "SCHOOL_CATEGORIES",
    "STRUCTURES",
    "STRUCTURE_CODES",
    "Row",
    "_PgConn",
    "_PgCursor",
    "_RE_INSERT",
    "_RE_JULIAN",
    "_RE_PRINTF",
    "_pg_row_factory",
    "_to_pg",
    "SCHEMA_VERSION",
    "_DROP_COLUMNS",
    "_MIGRATIONS",
    "_RENAME_COLUMNS",
    "_SCHOOL_TYPE_MAP",
    "_cols",
    "_fill_ref_codes",
    "_lookup_id",
    "_migrate_data",
    "_recompute_card_numbers",
    "_shift_school_category_ids",
    "_ORG_COLUMNS",
    "_TS_NOW",
    "_TS_SKIP",
    "_drop_org_horoo",
    "_ensure_timestamps",
    "_migrate",
    "_relax_submission_user",
    "pg_sync_sequences",
    "_PG_TS_FN",
    "_RE_FK",
    "_RE_ID_PK",
    "_RE_TABLE",
    "_pg_migrate",
    "_pg_schema",
    "_pg_tables",
    "_pg_timestamps",
    "_split_statements",
    "_strip_dangling_comma",
    "init_db",
    "REFERENCE_SEEDS",
    "seed_education_degree",
    "seed_position",
    "seed_profession",
    "seed_references",
    "seed_reward_type",
    "seed_salary_scale",
    "seed_school_category",
    "seed_structure",
    "_seed_coded_ref",
    "_seed_reference",
    "_utc_now_iso",
    "DEFAULT_MENUS",
    "DEFAULT_PORTAL_SETTINGS",
    "seed_menu",
    "seed_portal_settings",
    "seed_users",
    "seed",
    "seed_union",
    "_load_json",
    "ensure_seeded",
    "seed_all",
]
