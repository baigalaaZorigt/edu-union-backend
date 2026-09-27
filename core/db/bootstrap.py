"""Seed-ийн оруулах цэгүүд: seed_all() (`python -m core.db`) ба ensure_seeded() (апп эхлэхэд)."""

from core.db.pg_schema import pg_sync_sequences
from core.db.schema import init_db
from core.db.seed_ref import REFERENCE_SEEDS, count, seed_references
from core.db.seed_portal import seed_menu, seed_portal_settings, seed_users
from core.db.seed_data import seed, seed_union


def seed_all():
    """Бүх домэйны seed-г дараалан ажиллуулна (`python -m core.db` үүнийг дуудна).

    Лавлахууд эхэлнэ — seed_union() тэдгээрийн id-г (ж: school_category_id) заана.
    Схемийг эхлээд Alembic-ээр `head` хүртэл шинэчилнэ (хоосон DB бол үүсгэнэ).
    """
    migrate()
    seed()
    seed_references()
    seed_union()
    seed_menu()
    seed_portal_settings()
    seed_users()
    pg_sync_sequences()      # PG: гараас өгсөн id-ийн дараа дарааллыг тааруулна


def migrate():
    """Схемийг Alembic-ээр `head` хүртэл шинэчилнэ.

    Alembic-ээс ӨМНӨ үүссэн DB (alembic_version алга, гэхдээ хүснэгтүүд бий — production,
    хуучин локал файл): хуучин init_db()-ээр одоогийн схемд хүргээд baseline (0001)-ийг
    stamp хийнэ. Шинэ хоосон DB: 0001 өөрөө бүх схемийг үүсгэнэ. Дараа нь үргэлж
    `upgrade head` — шинэ migration-ууд (0002+) энд л хэрэгжинэ.
    """
    import os

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    import core.orm as orm
    from core.db import BASE_DIR

    cfg = Config(os.path.join(BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BASE_DIR, "alembic"))
    tables = set(inspect(orm.engine()).get_table_names())
    if "alembic_version" not in tables and "app_user" in tables:
        init_db()
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")


def ensure_seeded():
    """Хоосон хүснэгтүүдийг л автоматаар seed хийнэ. Idempotent.

    create_app() (run.py) эндээс дуудна — Render/Heroku зэрэг `python -m core.db`-г
    тусад нь ажиллуулдаггүй орчинд өгөгдөл (ж: эрхийн жагсаалт) хоосон үлдэхээс
    сэргийлнэ. Аль хэдийн seed хийсэн бол зөвхөн COUNT шалгаад өнгөрнө.
    """
    migrate()
    from core.orm import new_session
    s = new_session(include_deleted=True)
    try:
        def empty(table):
            return count(s, table) == 0

        need_units = empty("admin_unit1")
        need_ref = any(empty(table) for table, _ in REFERENCE_SEEDS)
        need_menu = empty("menu")
        need_settings = empty("portal_settings")
    finally:
        s.close()

    # Лавлахууд эхэлнэ — seed_union() тэдгээрийн id-г заадаг (school_category_id).
    if need_ref:
        seed_references()
    if need_units:
        seed()
        seed_union()
    if need_menu:
        seed_menu()
    if need_settings:
        seed_portal_settings()
    # Эрх/дүрийг ҮРГЭЛЖ синк хийнэ (idempotent): шинэ resource-ийн эрхүүд нэмэгдэж,
    # admin бүх эрхээ авна. Анхны admin хэрэглэгч зөвхөн app_user хоосон үед л үүснэ.
    seed_users()
    pg_sync_sequences()          # PG дээр id-ийн дараалал зөв байхыг баталгаажуулна
