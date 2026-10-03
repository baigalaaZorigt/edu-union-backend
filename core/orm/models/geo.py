"""ORM model: Засаг захиргааны нэгж ба сургуулийн ангилал.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class AdminUnit1(Base):
    __tablename__ = "admin_unit1"

    code: Mapped[str] = mapped_column(Str, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class AdminUnit2(Base):
    __tablename__ = "admin_unit2"
    __table_args__ = (
        Index('idx_au2_au1', 'au1_code'),
    )

    au2_code: Mapped[str] = mapped_column(Str, primary_key=True, autoincrement=False)
    au2_name: Mapped[str] = mapped_column(Str, nullable=False)
    au1_code: Mapped[str] = mapped_column(Str, ForeignKey("admin_unit1.code", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class AdminUnit3(Base):
    __tablename__ = "admin_unit3"
    __table_args__ = (
        Index('idx_au3_au1', 'au1_code'),
        Index('idx_au3_au2', 'au2_code'),
    )

    au3_code: Mapped[str] = mapped_column(Str, primary_key=True, autoincrement=False)
    au3_name: Mapped[str] = mapped_column(Str, nullable=False)
    au1_code: Mapped[str] = mapped_column(Str, ForeignKey("admin_unit1.code", ondelete="CASCADE"), nullable=False)
    au2_code: Mapped[str] = mapped_column(Str, ForeignKey("admin_unit2.au2_code", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class SchoolCategory(Base):
    __tablename__ = "school_category"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    full_name: Mapped[str] = mapped_column(Str, nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(Str)
    english_name: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
