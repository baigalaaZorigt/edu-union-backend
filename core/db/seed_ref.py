"""Лавлах хүснэгтүүдийн seed (REFERENCE_SEEDS-ийн дарааллаар)."""

from datetime import datetime, timezone

from core.db import get_db
from core.db.reference_data import (EDUCATION_DEGREES, POSITIONS, PROFESSIONS, REWARD_TYPES,
                                    SALARY_SCALE, SCHOOL_CATEGORIES, STRUCTURES,
                                    STRUCTURE_CODES)
from core.db.schema import init_db


def _utc_now_iso():
    """Одоогийн UTC цагийг ISO хэлбэрээр (секундийн нарийвчлалтай) буцаана."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _seed_reference(table, columns, rows, label, after_sql=None):
    """Лавлах хүснэгтэд мөрүүдийг INSERT OR IGNORE-оор ачаалж, тоог нь хэвлэнэ.

    after_sql өгвөл INSERT-ийн дараа (commit-оос өмнө) ажиллана — ж: хуучин DB-д
    NULL үлдсэн code-г дүүргэх.
    """
    init_db()
    conn = get_db()
    conn.executemany(
        f"INSERT OR IGNORE INTO {table}({', '.join(columns)}) "
        f"VALUES ({', '.join('?' * len(columns))})",
        rows)
    if after_sql:
        conn.execute(after_sql)
    conn.commit()
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    print(f"{label} ачаалагдлаа:", n)


def seed_education_degree():
    """Боловсролын зэргийн ангиллын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    _seed_reference("education_degree", ("id", "name"), EDUCATION_DEGREES,
                    "Боловсролын зэрэг")


def _seed_coded_ref(table, data, label):
    """id+name лавлахыг ачаалж, code-г 2 оронтой id-гаар (01, 02 ...) дүүргэнэ.

    Хуучин DB дээр code багана саяхан нэмэгдсэн тул NULL үлдсэн мөрүүдийг ч дүүргэнэ.
    """
    _seed_reference(
        table, ("id", "code", "name"), [(i, f"{i:02d}", name) for i, name in data], label,
        after_sql=f"UPDATE {table} SET code = printf('%02d', id) "
                  "WHERE code IS NULL OR code = ''")


def seed_position():
    """Албан тушаалын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    _seed_coded_ref("position", POSITIONS, "Албан тушаал")


def seed_profession():
    """Мэргэжлийн лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    _seed_coded_ref("profession", PROFESSIONS, "Мэргэжил")


def seed_reward_type():
    """Шагнал, урамшууллын төрлийн лавлахыг ачаална (давхардлыг алгасна)."""
    _seed_coded_ref("reward_type", REWARD_TYPES, "Шагнал, урамшууллын төрөл")


def seed_structure():
    """Бүтцийн удирдлагын лавлахыг ачаална (давхардлыг алгасна).

    Кодыг 2 оронтой id-гаар биш, эх хүснэгтийн № -оор (I, I.1, II.0 ...) бичнэ.
    """
    _seed_reference(
        "structure", ("id", "code", "name"),
        [(i, STRUCTURE_CODES.get(i, f"{i:02d}"), name) for i, name in STRUCTURES],
        "Бүтцийн удирдлага")


def seed_salary_scale():
    """Цалингийн шатлалын лавлах өгөгдлийг ачаална (kod-оор давхардлыг алгасна)."""
    _seed_reference("salary_scale", ("sector", "code", "position", "salary"),
                    SALARY_SCALE, "Цалингийн шатлал")


def seed_school_category():
    """Сургуулийн ангиллын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    _seed_reference("school_category", ("id", "full_name", "short_name", "english_name"),
                    SCHOOL_CATEGORIES, "Сургуулийн ангилал")


# Лавлахуудын seed — ЭНЭ дарааллаар (seed_all() ба ensure_seeded() хоёулаа ашиглана).
# seed_union() нь тэдгээрийн id-г (ж: school_category_id) заадаг тул түүнээс ӨМНӨ ажиллана.
REFERENCE_SEEDS = (
    ("school_category", seed_school_category),
    ("salary_scale", seed_salary_scale),
    ("education_degree", seed_education_degree),
    ("position", seed_position),
    ("profession", seed_profession),
    ("reward_type", seed_reward_type),
    ("structure", seed_structure),
)


def seed_references():
    """Бүх лавлах хүснэгтийг REFERENCE_SEEDS-ийн дарааллаар ачаална."""
    for _, seed_fn in REFERENCE_SEEDS:
        seed_fn()
