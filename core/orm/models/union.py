"""ORM model: Үйлдвэрчний эвлэл: холбоо, хороо, байгууллага, гишүүн, холбоо барих, цалин.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base


class Holboo(Base):
    __tablename__ = "holboo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Horoo(Base):
    __tablename__ = "horoo"
    __table_args__ = (
        Index('idx_horoo_holboo', 'holboo_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    holboo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holboo.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(Text)
    registration_number: Mapped[Optional[str]] = mapped_column(Text)
    founded_date: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    school_category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("school_category.id", ondelete="SET NULL"))
    org_code: Mapped[Optional[str]] = mapped_column(Text)
    registration_number: Mapped[Optional[str]] = mapped_column(Text)
    state_reg_number: Mapped[Optional[str]] = mapped_column(Text)
    founded_date: Mapped[Optional[str]] = mapped_column(Text)
    activity_code: Mapped[Optional[str]] = mapped_column(Text)
    activity_name: Mapped[Optional[str]] = mapped_column(Text)
    parent_org: Mapped[Optional[str]] = mapped_column(Text)
    au1_code: Mapped[Optional[str]] = mapped_column(Text)
    au2_code: Mapped[Optional[str]] = mapped_column(Text)
    au3_code: Mapped[Optional[str]] = mapped_column(Text)
    address_detail: Mapped[Optional[str]] = mapped_column(Text)
    postal_address: Mapped[Optional[str]] = mapped_column(Text)
    phone1: Mapped[Optional[str]] = mapped_column(Text)
    phone2: Mapped[Optional[str]] = mapped_column(Text)
    email: Mapped[Optional[str]] = mapped_column(Text)
    contact_name: Mapped[Optional[str]] = mapped_column(Text)
    structure_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("structure.id", ondelete="SET NULL"))
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Member(Base):
    __tablename__ = "member"
    __table_args__ = (
        Index('idx_member_org', 'organization_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[Optional[str]] = mapped_column(Text)
    gender: Mapped[Optional[str]] = mapped_column(Text)
    register_number: Mapped[Optional[str]] = mapped_column(Text)
    union_card_code: Mapped[Optional[str]] = mapped_column(Text)
    union_card_number: Mapped[Optional[str]] = mapped_column(Text)
    union_joined_date: Mapped[Optional[str]] = mapped_column(Text)
    member_status: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(Text)
    position_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("position.id", ondelete="SET NULL"))
    profession_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("profession.id", ondelete="SET NULL"))
    salary_scale_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("salary_scale.id", ondelete="SET NULL"))
    email: Mapped[Optional[str]] = mapped_column(Text)
    au1_code: Mapped[Optional[str]] = mapped_column(Text)
    au2_code: Mapped[Optional[str]] = mapped_column(Text)
    au3_code: Mapped[Optional[str]] = mapped_column(Text)
    address_detail: Mapped[Optional[str]] = mapped_column(Text)
    signature: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Contact(Base):
    __tablename__ = "contact"
    __table_args__ = (
        Index('idx_contact_owner', 'owner_type', 'owner_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class SalaryScale(Base):
    __tablename__ = "salary_scale"
    __table_args__ = (
        UniqueConstraint('code', name='salary_scale_code_key'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[Optional[str]] = mapped_column(Text)
    salary: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class SalaryRequest(Base):
    __tablename__ = "salary_request"
    __table_args__ = (
        Index('idx_salreq_member', 'member_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    salary_scale_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("salary_scale.id", ondelete="SET NULL"))
    sector: Mapped[Optional[str]] = mapped_column(Text)
    code: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[Optional[str]] = mapped_column(Text)
    salary: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'хүлээгдэж буй'::text"))
    request_date: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
