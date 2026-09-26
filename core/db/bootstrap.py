"""Seed-ийн оруулах цэгүүд: seed_all() (`python -m core.db`) ба ensure_seeded() (апп эхлэхэд)."""

from core.db import get_db
from core.db.pg_schema import pg_sync_sequences
from core.db.schema import init_db
from core.db.seed_ref import REFERENCE_SEEDS, seed_references
from core.db.seed_portal import seed_menu, seed_portal_settings, seed_users
from core.db.seed_data import seed, seed_union


def seed_all():
    """Бүх домэйны seed-г дараалан ажиллуулна (`python -m core.db` үүнийг дуудна).

    Лавлахууд эхэлнэ — seed_union() тэдгээрийн id-г (ж: school_category_id) заана.
    """
    seed()
    seed_references()
    seed_union()
    seed_menu()
    seed_portal_settings()
    seed_users()
    pg_sync_sequences()      # PG: гараас өгсөн id-ийн дараа дарааллыг тааруулна


def ensure_seeded():
    """Хоосон хүснэгтүүдийг л автоматаар seed хийнэ. Idempotent.

    create_app() (run.py) эндээс дуудна — Render/Heroku зэрэг `python -m core.db`-г
    тусад нь ажиллуулдаггүй орчинд өгөгдөл (ж: эрхийн жагсаалт) хоосон үлдэхээс
    сэргийлнэ. Аль хэдийн seed хийсэн бол зөвхөн COUNT шалгаад өнгөрнө.
    """
    init_db()
    conn = get_db()

    def empty(table):
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

    need_units = empty("admin_unit1")
    need_ref = any(empty(table) for table, _ in REFERENCE_SEEDS)
    need_menu = empty("menu")
    need_settings = empty("portal_settings")
    conn.close()

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
