"""ORM model: Судалгаа / санал асуулга.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import REAL, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class Form(Base):
    __tablename__ = "form"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    type: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'survey'::text"))
    title: Mapped[str] = mapped_column(Str, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Str)
    status: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'draft'::text"))
    start_at: Mapped[Optional[str]] = mapped_column(Str)
    end_at: Mapped[Optional[str]] = mapped_column(Str)
    show_results: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("1"))
    one_response: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("1"))
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)


class FormQuestion(Base):
    __tablename__ = "form_question"
    __table_args__ = (
        Index('idx_form_question_form', 'form_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    form_id: Mapped[int] = mapped_column(Int, ForeignKey("form.id", ondelete="CASCADE"), nullable=False)
    question_type: Mapped[str] = mapped_column(Str, nullable=False)
    title: Mapped[str] = mapped_column(Str, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Str)
    is_required: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    settings: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class FormOption(Base):
    __tablename__ = "form_option"
    __table_args__ = (
        Index('idx_form_option_question', 'question_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    question_id: Mapped[int] = mapped_column(Int, ForeignKey("form_question.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(Str, nullable=False)
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class FormDocument(Base):
    __tablename__ = "form_document"
    __table_args__ = (
        Index('idx_form_document_form', 'form_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    form_id: Mapped[int] = mapped_column(Int, ForeignKey("form.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(Str, nullable=False)
    file_path: Mapped[str] = mapped_column(Str, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(Str)
    file_size: Mapped[Optional[int]] = mapped_column(Int)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class FormSubmission(Base):
    __tablename__ = "form_submission"
    __table_args__ = (
        Index('idx_form_submission_form', 'form_id', 'user_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    form_id: Mapped[int] = mapped_column(Int, ForeignKey("form.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Int)
    submitted_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class FormAnswer(Base):
    __tablename__ = "form_answer"
    __table_args__ = (
        Index('idx_form_answer_question', 'question_id'),
        Index('idx_form_answer_submission', 'submission_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    submission_id: Mapped[int] = mapped_column(Int, ForeignKey("form_submission.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(Int, ForeignKey("form_question.id", ondelete="CASCADE"), nullable=False)
    text_value: Mapped[Optional[str]] = mapped_column(Str)
    numeric_value: Mapped[Optional[float]] = mapped_column(REAL)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class FormAnswerOption(Base):
    __tablename__ = "form_answer_option"
    __table_args__ = (
        Index('idx_form_answer_option_answer', 'answer_id'),
        Index('idx_form_answer_option_option', 'option_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    answer_id: Mapped[int] = mapped_column(Int, ForeignKey("form_answer.id", ondelete="CASCADE"), nullable=False)
    option_id: Mapped[int] = mapped_column(Int, ForeignKey("form_option.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
