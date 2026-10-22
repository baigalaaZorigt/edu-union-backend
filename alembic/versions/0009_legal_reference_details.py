"""legal_reference: doc_number, approved_date, summary, pdf_url, pdf_name

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

COLUMNS = ("doc_number", "approved_date", "summary", "pdf_url", "pdf_name")


def upgrade():
    # Бүгд nullable — одоогийн мөрүүд хэвээр ажиллана; урт/формат шалгалтыг API хийнэ.
    for name in COLUMNS:
        op.add_column("legal_reference", sa.Column(name, sa.Text))


def downgrade():
    with op.batch_alter_table("legal_reference") as batch:  # SQLite-д DROP COLUMN batch-аар
        for name in reversed(COLUMNS):
            batch.drop_column(name)
