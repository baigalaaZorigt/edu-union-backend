"""home_about (singleton) + home_about_cards — нүүр хуудасны «Холбооны тухай» хэсэг

backend-spec-home-about.md: portal-ийн app/page.tsx-д хатуу бичигдсэн текстийг админаас засдаг
болгоно. Сайт migration-ий дараа яг өмнөх шигээ харагдахын тулд singleton мөр (id=1) болон
3 картыг спекийн §4-ийн текстээр НЭГ УДАА бөглөнө (дараа нь админ устгасан картыг сэргээхгүй).
home_about.* эрхүүдийг seed_users() (PERMISSION_RESOURCES) үүсгэж админд онооно.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-31
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

TITLE = "Холбооны тухай"
BODY = (
    "Монголын Боловсрол, Шинжлэх Ухааны Үйлдвэрчний Эвлэлийн Холбоо нь боловсрол, шинжлэх "
    "ухааны салбарын ажилтнуудын хөдөлмөрлөх эрх, түүнтэй холбогдсон хууль ёсны ашиг сонирхлыг "
    "хамтран хамгаалах зорилгоор сайн дурын үндсэн дээр эвлэлдэн нэгдсэн байгууллага юм.\n\n"
    "Холбоо нь гишүүдийнхээ хөдөлмөрлөх эрхийг хамгаалах, нийгэм, эдийн засаг, оюуны эрх ашгийг "
    "хангах, салбарын бодлого шийдвэрт гишүүдийн дуу хоолойг хүргэх чиглэлээр ажилладаг."
)
CARDS = (
    ("Алсын хараа", "Боловсрол, шинжлэх ухааны хөгжлийг дэмжих замаар салбарын ажилтнуудын "
                    "хөдөлмөрийн үнэлэмжийг дээшлүүлэх."),
    ("Эрхэм зорилго", "Гишүүдийн хөдөлмөрлөх эрх, хууль ёсны ашиг сонирхлыг тууштай хамгаалах."),
    ("Үйл ажиллагааны зарчим", "Ардчилсан, ил тод, шударга байдал, эв санааны нэгдэл, хүний "
                               "эрхийг дээдлэх."),
)


def _audit():
    return [sa.Column("created_at", sa.Text),
            sa.Column("updated_at", sa.Text),
            sa.Column("deleted_at", sa.Text),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
            sa.Column("updated_by", sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL"))]


def upgrade():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    about = op.create_table(
        "home_about",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=sa.text("''")),
        *_audit(),
    )
    cards = op.create_table(
        "home_about_cards",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_visible", sa.Integer, nullable=False, server_default=sa.text("1")),
        *_audit(),
        sqlite_autoincrement=True,
    )
    op.create_index("idx_home_about_cards_order", "home_about_cards", ["is_visible", "sort_order"])

    op.bulk_insert(about, [{"id": 1, "title": TITLE, "body": BODY,
                            "created_at": now, "updated_at": now}])
    op.bulk_insert(cards, [{"title": t, "text": x, "sort_order": i, "is_visible": 1,
                            "created_at": now, "updated_at": now}
                           for i, (t, x) in enumerate(CARDS, start=1)])


def downgrade():
    op.drop_index("idx_home_about_cards_order", "home_about_cards")
    op.drop_table("home_about_cards")
    op.drop_table("home_about")
