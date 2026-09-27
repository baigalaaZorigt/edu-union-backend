"""ORM model: Порталын цэс, хуудас, блок, тохиргоо, баннер, хамтрагч.

Багана бүр production-ийн схемтэй таарна — хүснэгтийг model-оос биш
alembic/versions/0001_baseline үүсгэдэг. created_at/updated_at-ийг DB-ийн trigger бөглөнө.
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from core.orm.base import Base


class Menu(Base):
    __tablename__ = "menu"
    __table_args__ = (
        UniqueConstraint('slug', name='menu_slug_key'),
        Index('idx_menu_parent', 'parent_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("menu.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'page'::text"))
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("0"))
    is_visible: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("1"))
    external_url: Mapped[Optional[str]] = mapped_column(Text)
    news_category: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Page(Base):
    __tablename__ = "page"
    __table_args__ = (
        UniqueConstraint('menu_id', name='page_menu_id_key'),
        Index('idx_page_menu', 'menu_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    menu_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("menu.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[Optional[str]] = mapped_column(Text)
    cover_image: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'draft'::text"))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)


class PageBlock(Base):
    __tablename__ = "page_block"
    __table_args__ = (
        Index('idx_page_block_page', 'page_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("page.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("0"))
    text: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(Text)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    name: Mapped[Optional[str]] = mapped_column(Text)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    size: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class PortalSettings(Base):
    __tablename__ = "portal_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    header_title: Mapped[Optional[str]] = mapped_column(Text)
    header_subtitle: Mapped[Optional[str]] = mapped_column(Text)
    hero_badge: Mapped[Optional[str]] = mapped_column(Text)
    hero_title: Mapped[Optional[str]] = mapped_column(Text)
    hero_text: Mapped[Optional[str]] = mapped_column(Text)
    phones: Mapped[Optional[str]] = mapped_column(Text)
    website: Mapped[Optional[str]] = mapped_column(Text)
    facebook_url: Mapped[Optional[str]] = mapped_column(Text)
    youtube_url: Mapped[Optional[str]] = mapped_column(Text)
    address: Mapped[Optional[str]] = mapped_column(Text)
    map_embed_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Banner(Base):
    __tablename__ = "banner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_visible: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    starts_at: Mapped[Optional[str]] = mapped_column(Text)
    ends_at: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


class Partner(Base):
    __tablename__ = "partner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_visible: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[Optional[str]] = mapped_column(Text)
