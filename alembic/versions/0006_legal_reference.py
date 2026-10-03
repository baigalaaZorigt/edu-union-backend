"""legal_reference — Эрх зүйн дугаарласан мод (parent_id + sort_order; дугаар хадгалагдахгүй)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legal_reference",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("parent_id", sa.Integer,
                  sa.ForeignKey("legal_reference.id", ondelete="CASCADE")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_visible", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.Text),
        sa.Column("updated_at", sa.Text),
        sa.Column("deleted_at", sa.Text),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
        sqlite_autoincrement=True,
    )
    op.create_index("idx_legal_reference_parent", "legal_reference", ["parent_id", "sort_order"])


def downgrade():
    op.drop_table("legal_reference")
