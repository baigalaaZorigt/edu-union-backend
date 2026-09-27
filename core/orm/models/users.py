"""ORM model: Эрх, дүр, хэрэглэгч, хамрах хүрээ, нэвтрэх оролдлого.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class Permission(Base):
    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint('code', name='permission_code_key'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    code: Mapped[str] = mapped_column(Str, nullable=False)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(Str)
    action: Mapped[Optional[str]] = mapped_column(Str)
    description: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class Role(Base):
    __tablename__ = "role"
    __table_args__ = (
        UniqueConstraint('name', name='role_name_key'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(Str)
    description: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class RolePermission(Base):
    __tablename__ = "role_permission"
    __table_args__ = (
        Index('idx_rp_perm', 'permission_id'),
        Index('idx_rp_role', 'role_id'),
    )

    role_id: Mapped[int] = mapped_column(Int, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    permission_id: Mapped[int] = mapped_column(Int, ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint('username', name='app_user_username_key'),
        Index('idx_user_role', 'role_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    username: Mapped[str] = mapped_column(Str, nullable=False)
    password_hash: Mapped[str] = mapped_column(Str, nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(Str)
    first_name: Mapped[Optional[str]] = mapped_column(Str)
    email: Mapped[Optional[str]] = mapped_column(Str)
    role_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("role.id", ondelete="SET NULL"))
    structure_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("structure.id", ondelete="SET NULL"))
    is_active: Mapped[Optional[int]] = mapped_column(Int, server_default=text("1"))
    must_change_password: Mapped[Optional[int]] = mapped_column(Int, server_default=text("0"))
    onboarding_completed_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class UserScope(Base):
    __tablename__ = "user_scope"

    user_id: Mapped[int] = mapped_column(Int, ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    school_type: Mapped[Optional[str]] = mapped_column(Str)
    district_au2_code: Mapped[Optional[str]] = mapped_column(Str)
    organization_ids: Mapped[Optional[str]] = mapped_column(Str, server_default=text("'[]'::text"))
    organization_id: Mapped[Optional[int]] = mapped_column(Int)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class LoginAttempt(Base):
    __tablename__ = "login_attempt"
    __table_args__ = (
        Index('idx_login_attempt_ip', 'ip', 'created_at'),
        Index('idx_login_attempt_time', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    username: Mapped[str] = mapped_column(Str, nullable=False)
    ip: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[str] = mapped_column(Str, nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
