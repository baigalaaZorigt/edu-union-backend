"""аудит — created_by / updated_by (хэн үүсгэсэн, хэн зассан) + app_user.token_version

form, news-д аль хэдийн байсан. Утгыг ORM session өөрөө бөглөнө — core/orm/stamp.py.
token_version — нууц үг сэргээхэд +1; JWT-ийн `ver` claim таарахгүй бол 401.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = (
    'admin_unit1',
    'admin_unit2',
    'admin_unit3',
    'app_user',
    'banner',
    'complaints',
    'contact',
    'education_degree',
    'holboo',
    'horoo',
    'legal_document',
    'member',
    'member_education',
    'member_file',
    'member_reward',
    'menu',
    'organization',
    'partner',
    'portal_settings',
    'position',
    'profession',
    'reward_type',
    'role',
    'salary_scale',
    'school_category',
    'structure',
    'suggestions',
)
COLUMNS = ("created_by", "updated_by")


def upgrade():
    for table in TABLES:
        for col in COLUMNS:
            op.add_column(table, sa.Column(
                col, sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
                inline_references=True)      # SQLite: ADD CONSTRAINT байхгүй тул REFERENCES-ийг мөрд нь
    op.add_column("app_user", sa.Column("token_version", sa.Integer))


def downgrade():
    with op.batch_alter_table("app_user") as batch:
        batch.drop_column("token_version")
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            for col in COLUMNS:
                batch.drop_column(col)
