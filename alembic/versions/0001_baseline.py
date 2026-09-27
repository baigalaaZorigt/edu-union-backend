"""baseline — Alembic-ээс ӨМНӨХ бүх схем (44 хүснэгт, индекс, timestamp trigger).

Шинэ DB-д: core/db-ийн хуучин DDL-ийг (SCHEMA_* -> init_db; Postgres-д _pg_schema-аар
хөрвүүлнэ) ажиллуулна — production-тэй ЯГ ижил схем гарна.
Alembic-гүй үүссэн DB (production, хуучин локал): bootstrap.migrate() эхлээд хуучин
init_db()-ээр одоогийн төлөвт хүргээд энэ revision-ийг `stamp` хийнэ (дахин ажиллуулахгүй).
Цаашдын өөрчлөлт бүр ЭНЭ revision-ий дараах шинэ migration болно — SCHEMA_*-г засахгүй.

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from core.db.schema import init_db
    init_db()


def downgrade():
    raise NotImplementedError("baseline-ийг буцаах боломжгүй")
