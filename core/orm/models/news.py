"""ORM model: Мэдээ, санал хүсэлт / гомдол, мэдэгдэл.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        Index('idx_news_list', 'category', 'status'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    title: Mapped[str] = mapped_column(Str, nullable=False)
    category: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'Мэдээ'::text"))
    author: Mapped[Optional[str]] = mapped_column(Str)
    cover_image_url: Mapped[Optional[str]] = mapped_column(Str)
    summary: Mapped[Optional[str]] = mapped_column(Str)
    status: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'draft'::text"))
    published_at: Mapped[Optional[str]] = mapped_column(Str)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)


class NewsBlock(Base):
    __tablename__ = "news_block"
    __table_args__ = (
        Index('idx_news_block_news', 'news_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    news_id: Mapped[int] = mapped_column(Int, ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Str, nullable=False)
    sort_order: Mapped[Optional[int]] = mapped_column(Int, server_default=text("0"))
    text: Mapped[Optional[str]] = mapped_column(Str)
    url: Mapped[Optional[str]] = mapped_column(Str)
    title: Mapped[Optional[str]] = mapped_column(Str)
    caption: Mapped[Optional[str]] = mapped_column(Str)
    name: Mapped[Optional[str]] = mapped_column(Str)
    mime_type: Mapped[Optional[str]] = mapped_column(Str)
    size: Mapped[Optional[int]] = mapped_column(Int)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        Index('idx_suggestions_created', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    email: Mapped[str] = mapped_column(Str, nullable=False)
    phone: Mapped[str] = mapped_column(Str, nullable=False)
    message: Mapped[str] = mapped_column(Str, nullable=False)
    status: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'new'::text"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        Index('idx_complaints_created', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    email: Mapped[str] = mapped_column(Str, nullable=False)
    phone: Mapped[str] = mapped_column(Str, nullable=False)
    description: Mapped[str] = mapped_column(Str, nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(Str)
    file_name: Mapped[Optional[str]] = mapped_column(Str)
    status: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'new'::text"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index('idx_notify_status', 'status', 'scheduled_at'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    title: Mapped[str] = mapped_column(Str, nullable=False)
    body: Mapped[str] = mapped_column(Str, nullable=False)
    type: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'info'::text"))
    image_url: Mapped[Optional[str]] = mapped_column(Str)
    audience_type: Mapped[str] = mapped_column(Str, nullable=False)
    role_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("role.id", ondelete="SET NULL"))
    audience_user_ids: Mapped[Optional[str]] = mapped_column(Str)
    status: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'draft'::text"))
    scheduled_at: Mapped[Optional[str]] = mapped_column(Str)
    sent_at: Mapped[Optional[str]] = mapped_column(Str)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)



class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    __table_args__ = (
        UniqueConstraint('notification_id', 'user_id', name='notification_recipients_notification_id_user_id_key'),
        Index('idx_notify_rcpt_user', 'user_id', 'read_at'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    notification_id: Mapped[int] = mapped_column(Int, ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Int, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False)
    read_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
