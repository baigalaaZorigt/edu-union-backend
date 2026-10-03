"""ORM model: Порталын цэс, хуудас, блок, тохиргоо, баннер, хамтрагч.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base, Int, Str


class Menu(Base):
    __tablename__ = "menu"
    __table_args__ = (
        UniqueConstraint('slug', name='menu_slug_key'),
        Index('idx_menu_parent', 'parent_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("menu.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Str, nullable=False)
    slug: Mapped[str] = mapped_column(Str, nullable=False)
    type: Mapped[str] = mapped_column(Str, nullable=False, server_default=text("'page'::text"))
    sort_order: Mapped[Optional[int]] = mapped_column(Int, server_default=text("0"))
    is_visible: Mapped[Optional[int]] = mapped_column(Int, server_default=text("1"))
    external_url: Mapped[Optional[str]] = mapped_column(Str)
    news_category: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Page(Base):
    __tablename__ = "page"
    __table_args__ = (
        UniqueConstraint('menu_id', name='page_menu_id_key'),
        Index('idx_page_menu', 'menu_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    menu_id: Mapped[int] = mapped_column(Int, ForeignKey("menu.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Str)
    body: Mapped[Optional[str]] = mapped_column(Str)
    cover_image: Mapped[Optional[str]] = mapped_column(Str)
    status: Mapped[Optional[str]] = mapped_column(Str, server_default=text("'draft'::text"))
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class PageBlock(Base):
    __tablename__ = "page_block"
    __table_args__ = (
        Index('idx_page_block_page', 'page_id'),
    )

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    page_id: Mapped[int] = mapped_column(Int, ForeignKey("page.id", ondelete="CASCADE"), nullable=False)
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
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0007)



class PortalSettings(Base):
    __tablename__ = "portal_settings"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    logo_url: Mapped[Optional[str]] = mapped_column(Str)
    header_title: Mapped[Optional[str]] = mapped_column(Str)
    header_subtitle: Mapped[Optional[str]] = mapped_column(Str)
    hero_badge: Mapped[Optional[str]] = mapped_column(Str)
    hero_title: Mapped[Optional[str]] = mapped_column(Str)
    hero_text: Mapped[Optional[str]] = mapped_column(Str)
    phones: Mapped[Optional[str]] = mapped_column(Str)
    website: Mapped[Optional[str]] = mapped_column(Str)
    facebook_url: Mapped[Optional[str]] = mapped_column(Str)
    youtube_url: Mapped[Optional[str]] = mapped_column(Str)
    address: Mapped[Optional[str]] = mapped_column(Str)
    map_embed_url: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Banner(Base):
    __tablename__ = "banner"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(Str)
    image_url: Mapped[str] = mapped_column(Str, nullable=False)
    link_url: Mapped[Optional[str]] = mapped_column(Str)
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    is_visible: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("1"))
    starts_at: Mapped[Optional[str]] = mapped_column(Str)
    ends_at: Mapped[Optional[str]] = mapped_column(Str)
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))



class Partner(Base):
    __tablename__ = "partner"

    id: Mapped[int] = mapped_column(Int, primary_key=True)
    name: Mapped[str] = mapped_column(Str, nullable=False)
    url: Mapped[str] = mapped_column(Str, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(Str)
    sort_order: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("0"))
    is_visible: Mapped[int] = mapped_column(Int, nullable=False, server_default=text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Str)
    updated_at: Mapped[Optional[str]] = mapped_column(Str)
    logo_url: Mapped[Optional[str]] = mapped_column(Str)          # Alembic 0003 — /api/upload
    deleted_at: Mapped[Optional[str]] = mapped_column(Str)          # soft delete (0004)
    created_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))   # аудит (0005)
    updated_by: Mapped[Optional[int]] = mapped_column(Int, ForeignKey("app_user.id", ondelete="SET NULL"))
