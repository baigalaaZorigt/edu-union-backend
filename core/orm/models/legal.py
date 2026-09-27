"""ORM model: Хууль тогтоомж (legal_document) ба түүний блокууд (legal_document_block).

Alembic 0002-оор үүснэ (baseline-ийн хуучин DDL-д БАЙХГҮЙ тул trigger-гүй) — created_at /
updated_at-ийг ORM өөрөө бөглөнө, хуучин trigger-ийн форматтай ижил (UTC ISO, +00:00).
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


def utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LegalDocument(Base):
    __tablename__ = "legal_document"
    __table_args__ = (
        Index("idx_legal_document_order", "is_visible", "sort_order"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    title: Mapped[str] = mapped_column(Str, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(Str)            # Хууль / Дүрэм / Журам ...
    published_date: Mapped[Optional[str]] = mapped_column(Str)      # 'YYYY-MM-DD'
    source_name: Mapped[Optional[str]] = mapped_column(Str)         # legalinfo.mn, Холбоо
    display_mode: Mapped[str] = mapped_column(Str, nullable=False)  # link / file / detail
    external_url: Mapped[Optional[str]] = mapped_column(Str)
    pdf_url: Mapped[Optional[str]] = mapped_column(Str)
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    is_visible: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso)
    updated_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso, onupdate=utc_iso)


class LegalDocumentBlock(Base):
    __tablename__ = "legal_document_block"
    __table_args__ = (
        Index("idx_legal_block_doc", "legal_document_id", "sort_order"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    legal_document_id: Mapped[int] = mapped_column(
        Int, ForeignKey("legal_document.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Str, nullable=False)          # text / file / link
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    text: Mapped[Optional[str]] = mapped_column(Str)                # text
    url: Mapped[Optional[str]] = mapped_column(Str)                 # file / link
    title: Mapped[Optional[str]] = mapped_column(Str)               # link
    name: Mapped[Optional[str]] = mapped_column(Str)                # file
    mime_type: Mapped[Optional[str]] = mapped_column(Str)           # file
    size: Mapped[Optional[int]] = mapped_column(Int)                # file (байт)
    created_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso)
    updated_at: Mapped[Optional[str]] = mapped_column(Str, default=utc_iso, onupdate=utc_iso)
