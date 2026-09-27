"""ORM model: Үйлдвэрчний эвлэл: холбоо, хороо, байгууллага, гишүүн, холбоо барих, цалин.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class Holboo(Base):
    __tablename__ = "holboo"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class Horoo(Base):
    __tablename__ = "horoo"
    __table_args__ = (
        Index('idx_horoo_holboo', 'holboo_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    holboo_id: Mapped[int] = mapped_column(Int, ForeignKey("holboo.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(Str)
    registration_number: Mapped[Optional[str]] = mapped_column(Str)
    founded_date: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    school_category_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("school_category.id", ondelete="SET NULL"))
    org_code: Mapped[Optional[str]] = mapped_column(Str)
    registration_number: Mapped[Optional[str]] = mapped_column(Str)
    state_reg_number: Mapped[Optional[str]] = mapped_column(Str)
    founded_date: Mapped[Optional[str]] = mapped_column(Str)
    activity_code: Mapped[Optional[str]] = mapped_column(Str)
    activity_name: Mapped[Optional[str]] = mapped_column(Str)
    parent_org: Mapped[Optional[str]] = mapped_column(Str)
    au1_code: Mapped[Optional[str]] = mapped_column(Str)
    au2_code: Mapped[Optional[str]] = mapped_column(Str)
    au3_code: Mapped[Optional[str]] = mapped_column(Str)
    address_detail: Mapped[Optional[str]] = mapped_column(Str)
    postal_address: Mapped[Optional[str]] = mapped_column(Str)
    phone1: Mapped[Optional[str]] = mapped_column(Str)
    phone2: Mapped[Optional[str]] = mapped_column(Str)
    email: Mapped[Optional[str]] = mapped_column(Str)
    contact_name: Mapped[Optional[str]] = mapped_column(Str)
    structure_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("structure.id", ondelete="SET NULL"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class Member(Base):
    __tablename__ = "member"
    __table_args__ = (
        Index('idx_member_org', 'organization_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Int, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(Str)
    first_name: Mapped[str] = mapped_column(Str, nullable=False)
    birth_date: Mapped[Optional[str]] = mapped_column(Str)
    gender: Mapped[Optional[str]] = mapped_column(Str)
    register_number: Mapped[Optional[str]] = mapped_column(Str)
    union_card_code: Mapped[Optional[str]] = mapped_column(Str)
    union_card_number: Mapped[Optional[str]] = mapped_column(Str)
    union_joined_date: Mapped[Optional[str]] = mapped_column(Str)
    member_status: Mapped[Optional[str]] = mapped_column(Str)
    status: Mapped[Optional[str]] = mapped_column(Str)
    position_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("position.id", ondelete="SET NULL"))
    profession_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("profession.id", ondelete="SET NULL"))
    salary_scale_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("salary_scale.id", ondelete="SET NULL"))
    email: Mapped[Optional[str]] = mapped_column(Str)
    au1_code: Mapped[Optional[str]] = mapped_column(Str)
    au2_code: Mapped[Optional[str]] = mapped_column(Str)
    au3_code: Mapped[Optional[str]] = mapped_column(Str)
    address_detail: Mapped[Optional[str]] = mapped_column(Str)
    signature: Mapped[Optional[int]] = mapped_column(Int, server_default=text("0"))
    is_active: Mapped[Optional[int]] = mapped_column(Int, server_default=text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class Contact(Base):
    __tablename__ = "contact"
    __table_args__ = (
        Index('idx_contact_owner', 'owner_type', 'owner_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    owner_type: Mapped[str] = mapped_column(Str, nullable=False)
    owner_id: Mapped[int] = mapped_column(Int, nullable=False)
    type: Mapped[str] = mapped_column(Str, nullable=False)
    value: Mapped[str] = mapped_column(Str, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class SalaryScale(Base):
    __tablename__ = "salary_scale"
    __table_args__ = (
        UniqueConstraint('code', name='salary_scale_code_key'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    sector: Mapped[str] = mapped_column(Str, nullable=False)
    code: Mapped[str] = mapped_column(Str, nullable=False)
    position: Mapped[Optional[str]] = mapped_column(Str)
    salary: Mapped[Optional[int]] = mapped_column(Int)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class SalaryRequest(Base):
    __tablename__ = "salary_request"
    __table_args__ = (
        Index('idx_salreq_member', 'member_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    member_id: Mapped[int] = mapped_column(Int, ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    salary_scale_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("salary_scale.id", ondelete="SET NULL"))
    sector: Mapped[Optional[str]] = mapped_column(Str)
    code: Mapped[Optional[str]] = mapped_column(Str)
    position: Mapped[Optional[str]] = mapped_column(Str)
    salary: Mapped[Optional[int]] = mapped_column(Int)
    status: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'хүлээгдэж буй'::text"))
    request_date: Mapped[Optional[str]] = mapped_column(Str)
    note: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
