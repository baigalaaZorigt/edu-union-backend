"""legal_document + legal_document_block (Хууль тогтоомж)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legal_document",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("category", sa.Text),
        sa.Column("published_date", sa.Text),
        sa.Column("source_name", sa.Text),
        sa.Column("display_mode", sa.Text, nullable=False),
        sa.Column("external_url", sa.Text),
        sa.Column("pdf_url", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_visible", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.Text),
        sa.Column("updated_at", sa.Text),
        sqlite_autoincrement=True,
    )
    op.create_index("idx_legal_document_order", "legal_document", ["is_visible", "sort_order"])
    op.create_table(
        "legal_document_block",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("legal_document_id", sa.Integer,
                  sa.ForeignKey("legal_document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("text", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("name", sa.Text),
        sa.Column("mime_type", sa.Text),
        sa.Column("size", sa.Integer),
        sa.Column("created_at", sa.Text),
        sa.Column("updated_at", sa.Text),
        sqlite_autoincrement=True,
    )
    op.create_index("idx_legal_block_doc", "legal_document_block",
                    ["legal_document_id", "sort_order"])


def downgrade():
    op.drop_table("legal_document_block")
    op.drop_table("legal_document")
