"""ORM model: ҮЭ-ийн лавлах хүснэгтүүд ба гишүүний дэд мэдээлэл.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class EducationDegree(Base):
    __tablename__ = "education_degree"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Position(Base):
    __tablename__ = "position"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(Str)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Profession(Base):
    __tablename__ = "profession"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(Str)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class RewardType(Base):
    __tablename__ = "reward_type"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(Str)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(Str)            # ангилал (0008), чөлөөт текст
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Structure(Base):
    __tablename__ = "structure"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(Str)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class MemberEducation(Base):
    __tablename__ = "member_education"
    __table_args__ = (
        Index('idx_medu_member', 'member_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    member_id: Mapped[int] = mapped_column(Int, ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    education_degree_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("education_degree.id", ondelete="SET NULL"))
    school: Mapped[Optional[str]] = mapped_column(Str)
    profession: Mapped[Optional[str]] = mapped_column(Str)
    graduation_year: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class MemberReward(Base):
    __tablename__ = "member_reward"
    __table_args__ = (
        Index('idx_mreward_member', 'member_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    member_id: Mapped[int] = mapped_column(Int, ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    reward_type_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("reward_type.id", ondelete="SET NULL"))
    description: Mapped[Optional[str]] = mapped_column(Str)
    reward_date: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class MemberFile(Base):
    __tablename__ = "member_file"
    __table_args__ = (
        UniqueConstraint('stored_name', name='member_file_stored_name_key'),
        Index('idx_mfile_member', 'member_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    member_id: Mapped[int] = mapped_column(Int, ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(Str, nullable=False)
    stored_name: Mapped[str] = mapped_column(Str, nullable=False)
    size: Mapped[Optional[int]] = mapped_column(Int)
    note: Mapped[Optional[str]] = mapped_column(Str)
    uploaded_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
