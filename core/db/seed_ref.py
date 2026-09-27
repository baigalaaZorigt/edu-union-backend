"""Лавлах хүснэгтүүдийн seed (REFERENCE_SEEDS-ийн дарааллаар) — ORM-оор."""

from datetime import datetime, timezone

from sqlalchemy import func, insert, or_, select

from core.db.reference_data import (EDUCATION_DEGREES, POSITIONS, PROFESSIONS, REWARD_TYPES,
                                    SALARY_SCALE, SCHOOL_CATEGORIES, STRUCTURES,
                                    STRUCTURE_CODES)


def _utc_now_iso():
    """Одоогийн UTC цагийг ISO хэлбэрээр (секундийн нарийвчлалтай) буцаана."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _table(name):
    import importlib
    importlib.import_module("core.orm.models")    # бүх model metadata-д бүртгэгдэнэ
    from core.orm.base import Base
    return Base.metadata.tables[name]


def _unique_keys(table):
    """Хүснэгтийн давхцаж болох түлхүүрүүд: PK + UNIQUE хязгаарлалт + unique индекс."""
    keys = [tuple(c.name for c in table.primary_key.columns)]
    for con in table.constraints:
        if type(con).__name__ == "UniqueConstraint":
            keys.append(tuple(c.name for c in con.columns))
    for ix in table.indexes:
        if ix.unique:
            keys.append(tuple(c.name for c in ix.columns))
    return keys


def insert_missing(s, table, rows):
    """`INSERT OR IGNORE`-ийн ORM хувилбар: аль нэг PK/UNIQUE түлхүүр нь давхцах мөрийг
    алгасаад үлдсэнийг нэг дор оруулна. `table` — хүснэгтийн нэр, `rows` — dict-үүд.

    SQLite-ийн адил NULL агуулсан түлхүүр давхцалд тооцогдохгүй. Оруулсан мөрийн тоог буцаана.
    """
    t = _table(table)
    keys = [k for k in _unique_keys(t) if rows and all(c in rows[0] for c in k)]
    seen = {k: {tuple(r) for r in s.execute(select(*[t.c[c] for c in k]))} for k in keys}
    fresh = []
    for row in rows:
        vals = {k: tuple(row[c] for c in k) for k in keys}
        if any(None not in v and v in seen[k] for k, v in vals.items()):
            continue
        for k, v in vals.items():
            seen[k].add(v)
        fresh.append(row)
    if fresh:
        s.execute(insert(t), fresh)
    return len(fresh)


def count(s, table):
    """Хүснэгтийн мөрийн тоо."""
    return s.scalar(select(func.count()).select_from(_table(table)))


def _seed_reference(table, columns, rows, label, fix=None):
    """Лавлах хүснэгтэд мөрүүдийг (давхардлыг алгасаж) ачаалж, тоог нь хэвлэнэ.

    fix(session) өгвөл оруулсны дараа (commit-оос өмнө) ажиллана — ж: хуучин DB-д
    NULL үлдсэн code-г дүүргэх.
    """
    from core.orm import new_session
    s = new_session()
    try:
        insert_missing(s, table, [dict(zip(columns, r)) for r in rows])
        if fix:
            fix(s)
        s.commit()
        n = count(s, table)
    finally:
        s.close()
    print(f"{label} ачаалагдлаа:", n)


def seed_education_degree():
    """Боловсролын зэргийн ангиллын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    _seed_reference("education_degree", ("id", "name"), EDUCATION_DEGREES,
                    "Боловсролын зэрэг")


def _fill_codes(table):
    """code нь хоосон мөрүүдэд 2 оронтой id (01, 02 ...) бичих fix."""
    def fix(s):
        t = _table(table)
        for rid, in s.execute(select(t.c.id).where(or_(t.c.code.is_(None), t.c.code == ""))):
            s.execute(t.update().where(t.c.id == rid).values(code=f"{rid:02d}"))
    return fix


def _seed_coded_ref(table, data, label):
    """id+name лавлахыг ачаалж, code-г 2 оронтой id-гаар (01, 02 ...) дүүргэнэ.

    Хуучин DB дээр code багана саяхан нэмэгдсэн тул NULL үлдсэн мөрүүдийг ч дүүргэнэ.
    """
    _seed_reference(table, ("id", "code", "name"),
                    [(i, f"{i:02d}", name) for i, name in data], label, fix=_fill_codes(table))


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
