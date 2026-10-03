"""аудит — created_by / updated_by-г ҮЛДСЭН бүх хүснэгтэд (login_attempt-аас бусад)

0005 үндсэн жагсаалтуудад нэмсэн; энд дэд мөрүүд (блок, асуулт, сонголт, хариулт, хүрээ,
дүрийн эрх ...). Утгыг ORM session бөглөнө — core/orm/stamp.py.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

BOTH = (
    'form_answer',
    'form_answer_option',
    'form_document',
    'form_option',
    'form_question',
    'form_submission',
    'legal_document_block',
    'news_block',
    'notification_recipients',
    'page',
    'page_block',
    'permission',
    'role_permission',
    'salary_request',
    'user_scope',
)
ADD = [(t, c) for t in BOTH for c in ("created_by", "updated_by")] + [("notifications", "updated_by")]


def upgrade():
    for table, col in ADD:
        op.add_column(table, sa.Column(
            col, sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
            inline_references=True)


def downgrade():
    for table, col in ADD:
        with op.batch_alter_table(table) as batch:
            batch.drop_column(col)
