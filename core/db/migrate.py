"""Хуучин SQLite DB-г шинэчлэх: хүснэгт дахин үүсгэх, _migrate(), created_at/updated_at trigger."""

from core.db.migrate_data import (_DROP_COLUMNS, _MIGRATIONS, _RENAME_COLUMNS, _cols,
                                  _migrate_data)


def _relax_submission_user(conn):
    """form_submission.user_id-г NOT NULL байснаас NULL зөвшөөрөх болгож сулруулна.

    Портал нээлттэй болсноор зочин (нэвтрээгүй) хүн ч бөглөдөг болсон. SQLite
    баганы NOT NULL хязгаарыг ALTER-аар авч чаддаггүй тул хүснэгтийг дахин барина.
    DROP TABLE нь foreign_keys pragma асаалттай үед form_answer руу cascade хийчихдэг
    тул үйлдлийн турш pragma-г унтраана (шинэ DB дээр энэ функц юу ч хийхгүй).
    """
    info = {r[1]: r for r in conn.execute("PRAGMA table_info(form_submission)")}
    if "user_id" not in info or not info["user_id"][3]:   # notnull=0 бол хийх зүйлгүй
        return
    conn.commit()                       # PRAGMA нь гүйлгээний ГАДНА л үйлчилнэ
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE form_submission_new (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id      INTEGER NOT NULL,
            user_id      INTEGER,
            submitted_at TEXT,
            created_at   TEXT,
            FOREIGN KEY (form_id) REFERENCES form(id) ON DELETE CASCADE
        );
        INSERT INTO form_submission_new(id, form_id, user_id, submitted_at, created_at)
            SELECT id, form_id, user_id, submitted_at, created_at FROM form_submission;
        DROP TABLE form_submission;
        ALTER TABLE form_submission_new RENAME TO form_submission;
        CREATE INDEX IF NOT EXISTS idx_form_submission_form
            ON form_submission(form_id, user_id);
    """)
    conn.execute("PRAGMA foreign_keys = ON")


# organization-ы шинэ баганын жагсаалт (horoo_id-гүй) — _drop_org_horoo() ашиглана.
_ORG_COLUMNS = [
    "id", "name", "school_category_id", "org_code", "registration_number",
    "state_reg_number", "founded_date", "activity_code", "activity_name", "parent_org",
    "au1_code", "au2_code", "au3_code", "address_detail", "postal_address",
    "phone1", "phone2", "email", "contact_name", "structure_id",
    "created_at", "updated_at",
]


def _drop_org_horoo(conn):
    """organization.horoo_id-г бүрмөсөн хасна (хүснэгтийг дахин барьж).

    SQLite нь FK тодорхойлолтод оролцож буй баганыг ALTER TABLE DROP COLUMN-оор
    хасч чаддаггүй тул: шинэ хүснэгт барь -> өгөгдлийг хуул -> хуучныг устга ->
    нэрийг нь сольё. DROP TABLE нь foreign_keys pragma асаалттай үед member руу
    cascade хийчихдэг тул үйлдлийн турш pragma-г унтраана.
    """
    if "horoo_id" not in _cols(conn, "organization"):
        return
    cols = [c for c in _ORG_COLUMNS if c in _cols(conn, "organization")]
    cl = ", ".join(cols)
    conn.commit()                       # PRAGMA нь гүйлгээний ГАДНА л үйлчилнэ
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(f"""
        CREATE TABLE organization_new (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL,
            school_category_id  INTEGER,
            org_code            TEXT,
            registration_number TEXT,
            state_reg_number    TEXT,
            founded_date        TEXT,
            activity_code       TEXT,
            activity_name       TEXT,
            parent_org          TEXT,
            au1_code            TEXT,
            au2_code            TEXT,
            au3_code            TEXT,
            address_detail      TEXT,
            postal_address      TEXT,
            phone1              TEXT,
            phone2              TEXT,
            email               TEXT,
            contact_name        TEXT,
            structure_id        INTEGER,
            created_at          TEXT,
            updated_at          TEXT,
            FOREIGN KEY (school_category_id) REFERENCES school_category(id) ON DELETE SET NULL,
            FOREIGN KEY (structure_id) REFERENCES structure(id) ON DELETE SET NULL
        );
        INSERT INTO organization_new({cl}) SELECT {cl} FROM organization;
        DROP TABLE organization;
        ALTER TABLE organization_new RENAME TO organization;
    """)
    conn.execute("PRAGMA foreign_keys = ON")


def _migrate(conn):
    # 0) Галиглал -> англи нэр солих (дутуу багана нэмэхээс ӨМНӨ)
    for table, renames in _RENAME_COLUMNS.items():
        existing = _cols(conn, table)
        for old, new in renames:
            if old in existing and new not in existing:
                conn.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")
    # 1) Дутуу багана нэмэх
    for table, cols in _MIGRATIONS.items():
        existing = _cols(conn, table)
        for name, decl in cols:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    # 2) address -> address_detail нэр солих, эс бөгөөс address_detail-г шинээр нэмэх
    for table in ("organization", "member"):
        existing = _cols(conn, table)
        if "address" in existing and "address_detail" not in existing:
            conn.execute(f"ALTER TABLE {table} RENAME COLUMN address TO address_detail")
        elif "address_detail" not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN address_detail TEXT")
    # 3) form_submission.user_id-г NULL зөвшөөрөхөөр сулруулах (зочны бөглөлт)
    _relax_submission_user(conn)
    # 3.1) organization.horoo_id-г бүрмөсөн хасах (хүснэгтийг дахин барина)
    _drop_org_horoo(conn)
    # 4) Хуучин баганы утгыг шинэ бүтэц рүү зөөх (устгахаас өмнө)
    _migrate_data(conn)
    # 5) Хэрэглэхгүй болсон баганыг устгах
    for table, drops in _DROP_COLUMNS.items():
        existing = _cols(conn, table)
        for name in drops:
            if name in existing:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")


# --- created_at / updated_at: БҮХ хүснэгтэд ---
# Хүснэгт бүрт багана нэмээд, INSERT/UPDATE бүрд автоматаар бөглөх trigger тавина.
# Ингэснээр аль ч маршрут (одоогийн ба ирээдүйн) нэмэлт код бичихгүйгээр
# огноогоо авна. PRAGMA recursive_triggers анхдагчаараа OFF тул trigger дотор
# хийсэн UPDATE нь trigger-ийг дахин ажиллуулахгүй (давталт үүсэхгүй).
_TS_SKIP = {"sqlite_sequence"}
# menu/page/form зэрэг хүснэгтэд код нь өөрөө ISO огноо бичдэг — түүнтэй ижил хэлбэр.
_TS_NOW = "strftime('%Y-%m-%dT%H:%M:%S+00:00','now')"


def _ensure_timestamps(conn):
    """Хүснэгт бүрт created_at/updated_at багана ба тэдгээрийн trigger-ийг бэлтгэнэ.

    Хуучин мөрүүд NULL хэвээр үлдэнэ (жинхэнэ огноог нь мэдэх аргагүй) — зөвхөн
    эндээс хойшхи INSERT/UPDATE тэмдэглэгдэнэ.
    """
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name <> 'alembic_version'")]                                 # Alembic-ийн хүснэгт биш
    for t in tables:
        if t in _TS_SKIP:
            continue
        cols = _cols(conn, t)
        for col in ("created_at", "updated_at"):
            if col not in cols:
                conn.execute(f"ALTER TABLE {t} ADD COLUMN {col} TEXT")
        # INSERT: код нь өөрөө утга өгсөн бол түүнийг нь хүндэтгэнэ (COALESCE)
        conn.execute(
            f"CREATE TRIGGER IF NOT EXISTS trg_{t}_created AFTER INSERT ON {t} BEGIN "
            f"  UPDATE {t} SET created_at = COALESCE(NEW.created_at, {_TS_NOW}), "
            f"                 updated_at = COALESCE(NEW.updated_at, {_TS_NOW}) "
            f"   WHERE rowid = NEW.rowid; END")
        conn.execute(
            f"CREATE TRIGGER IF NOT EXISTS trg_{t}_updated AFTER UPDATE ON {t} BEGIN "
            f"  UPDATE {t} SET updated_at = {_TS_NOW} WHERE rowid = NEW.rowid; END")
