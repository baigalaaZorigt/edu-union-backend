"""soft delete — бүх хүснэгтэд deleted_at (UTC ISO; NULL = идэвхтэй)

news, form-д аль хэдийн байсан. Устгах үйлдэл мөрийг ХАДГАЛААД deleted_at-ийг бөглөнө,
бүх уншилт NULL-ийг л харна — core/orm/soft.py.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
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
    'form_answer',
    'form_answer_option',
    'form_document',
    'form_option',
    'form_question',
    'form_submission',
    'holboo',
    'horoo',
    'legal_document',
    'legal_document_block',
    'login_attempt',
    'member',
    'member_education',
    'member_file',
    'member_reward',
    'menu',
    'news_block',
    'notification_recipients',
    'notifications',
    'organization',
    'page',
    'page_block',
    'partner',
    'permission',
    'portal_settings',
    'position',
    'profession',
    'reward_type',
    'role',
    'role_permission',
    'salary_request',
    'salary_scale',
    'school_category',
    'structure',
    'suggestions',
    'user_scope',
)


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.Text))


def downgrade():
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("deleted_at")
