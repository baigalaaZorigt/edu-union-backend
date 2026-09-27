"""partner.logo_url — хамтрагч байгууллагын лого зураг

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("partner", sa.Column("logo_url", sa.Text))


def downgrade():
    with op.batch_alter_table("partner") as batch:     # SQLite-д DROP COLUMN batch-аар
        batch.drop_column("logo_url")
