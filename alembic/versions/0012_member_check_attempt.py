"""member_check_attempt — нээлттэй гишүүн шалгах endpoint-ийн IP тоолуур

member-check-spec.md: POST /api/member_check-ийн хязгаар бүх gunicorn ажилтанд нэг байж,
restart-д тэглэгдэхгүйн тулд DB-д (login_attempt-ийн хэв маяг). Зөвхөн шинэ хүснэгт нэмнэ.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "member_check_attempt",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ip", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.Text),
    )
    op.create_index("idx_member_check_attempt_ip", "member_check_attempt", ["ip", "created_at"])
    op.create_index("idx_member_check_attempt_time", "member_check_attempt", ["created_at"])


def downgrade():
    op.drop_index("idx_member_check_attempt_time", "member_check_attempt")
    op.drop_index("idx_member_check_attempt_ip", "member_check_attempt")
    op.drop_table("member_check_attempt")
