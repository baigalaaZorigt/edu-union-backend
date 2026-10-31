"""ORM model: нүүр хуудасны «Холбооны тухай» хэсэг — home_about (singleton) + home_about_cards.

Alembic 0011-ээр үүснэ (trigger-гүй) — created_at / updated_at-ийг ORM өөрөө бөглөнө
(legal_document-тай ижил UTC ISO формат).
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, text as sa_text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str
from core.orm.models.legal import utc_iso


class HomeAbout(Base):
    __tablename__ = "home_about"

    id: Mapped[int] = mapped_column(Int, primary_key=True)          # үргэлж 1
    title: Mapped[str] = mapped_column(Str, nullable=False)
    body: Mapped[str] = mapped_column(Str, nullable=False, server_default=sa_text("''"))
    created_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso)
    updated_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso, onupdate=utc_iso)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))


class HomeAboutCard(Base):
    __tablename__ = "home_about_cards"
    __table_args__ = (
        Index("idx_home_about_cards_order", "is_visible", "sort_order"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    title: Mapped[str] = mapped_column(Str, nullable=False)
    text: Mapped[str] = mapped_column(Str, nullable=False)
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=sa_text("0"))
    is_visible: Mapped[int] = mapped_column(Int, nullable=False, server_default=sa_text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso)
    updated_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso, onupdate=utc_iso)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
