"""SQLite холболт ба бүтэц (schema) үүсгэх, JSON өгөгдлийг ачаалах."""
import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "admin_units.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_unit1 (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_unit2 (
    au2_code TEXT PRIMARY KEY,
    au2_name TEXT NOT NULL,
    au1_code TEXT NOT NULL,
    FOREIGN KEY (au1_code) REFERENCES admin_unit1(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_unit3 (
    au3_code TEXT PRIMARY KEY,
    au3_name TEXT NOT NULL,
    au1_code TEXT NOT NULL,
    au2_code TEXT NOT NULL,
    FOREIGN KEY (au1_code) REFERENCES admin_unit1(code) ON DELETE CASCADE,
    FOREIGN KEY (au2_code) REFERENCES admin_unit2(au2_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_au2_au1 ON admin_unit2(au1_code);
CREATE INDEX IF NOT EXISTS idx_au3_au2 ON admin_unit3(au2_code);
CREATE INDEX IF NOT EXISTS idx_au3_au1 ON admin_unit3(au1_code);
"""

# ---------- Үйлдвэрчний эвлэлийн бүтэц (4 түвшин + холбоо барих) ----------
# holboo (Холбоо) -> horoo (Хороо) -> organization (Гишүүн байгууллага) -> member (Гишүүн)
# contact (Холбоо барих) нь хороо ЭСВЭЛ байгууллагад полиморфоор харьяалагдана.
SCHEMA_UNION = """
CREATE TABLE IF NOT EXISTS holboo (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL                       -- Холбооны нэр
);

CREATE TABLE IF NOT EXISTS horoo (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    holboo_id INTEGER NOT NULL,              -- Аль холбоонд харьяалагдах
    name      TEXT NOT NULL,                 -- Хорооны нэр
    FOREIGN KEY (holboo_id) REFERENCES holboo(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organization (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    horoo_id            INTEGER NOT NULL,    -- Аль хороонд харьяалагдах
    name                TEXT NOT NULL,       -- Байгууллагын нэр
    org_type            TEXT,                -- Сургууль / Цэцэрлэг / Эмнэлэг ...
    school_type         TEXT,               -- Их сургууль / СӨБ / ЕБС / МСҮТ (зөвхөн сургуульд)
    registration_number TEXT,               -- Регистрийн дугаар
    founded_date        TEXT,               -- Үүсгэн байгуулагдсан огноо (YYYY-MM-DD)
    activity_code       TEXT,               -- Үйл ажиллагааны чиглэлийн код
    activity_name       TEXT,               -- Үндсэн үйл ажиллагааны чиглэл
    parent_org          TEXT,               -- Толгой байгууллага
    address             TEXT,               -- Дэлгэрэнгүй хаяг
    FOREIGN KEY (horoo_id) REFERENCES horoo(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id   INTEGER NOT NULL,      -- Аль гишүүн байгууллагад харьяалагдах (FK)
    name              TEXT NOT NULL,         -- 1. Овог нэр
    birth_date        TEXT,                  -- 2. Төрсөн он (YYYY-MM-DD)
    gender            TEXT,                  -- 3. Хүйс ('эр' / 'эм')
    register_number   TEXT,                  -- 4. Регистрийн дугаар
    ue_batlamj_number TEXT,                  -- 5. ҮЭ-ийн батламжийн дугаар
    ue_joined_date    TEXT,                  -- 6. ҮЭ-д элссэн он сар өдөр (YYYY-MM-DD)
    member_status     TEXT,                  -- 7. ҮЭ-ийн гишүүний статус
    albn_tushaal      TEXT,                  -- 8. Эрхэлж байгаа ажил, албан тушаал
    mergejil          TEXT,                  -- 9. Мэргэжил
    bolovsrol         TEXT,                  -- 10. Боловсрол
    phone_fax         TEXT,                  -- 11. Факс, утасны дугаарууд
    address           TEXT,                  -- 12. Оршин суугаа хаяг
    signature         INTEGER DEFAULT 0,     -- Гарын үсэг байгаа эсэх (0/1)
    FOREIGN KEY (organization_id) REFERENCES organization(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contact (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_type TEXT NOT NULL,                -- 'horoo' эсвэл 'organization'
    owner_id   INTEGER NOT NULL,            -- Эзэмшигчийн id
    type       TEXT NOT NULL,               -- 'утас' / 'факс' / 'и-мэйл'
    value      TEXT NOT NULL,               -- 99112233, info@example.mn
    note       TEXT                         -- "захиргаа", "нягтлан" (сонголтоор)
);

-- Цалингийн шатлал (лавлах) — tsalin_husnegt.xlsx-аас
CREATE TABLE IF NOT EXISTS salary_scale (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    salbar       TEXT NOT NULL,               -- Салбар
    kod          TEXT NOT NULL UNIQUE,        -- Код (ТҮБД-5 гэх мэт)
    albn_tushaal TEXT,                        -- Албан тушаал
    tsalin       INTEGER                      -- Цалин (төгрөг)
);

CREATE TABLE IF NOT EXISTS salary_request (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id       INTEGER NOT NULL,         -- Аль гишүүний цалингийн хүсэлт
    salary_scale_id INTEGER,                  -- Сонгосон цалингийн шатлал (FK, snapshot хийгдэнэ)
    salbar          TEXT,                     -- Салбар (шатлалаас хуулагдана)
    kod             TEXT,                     -- Код (шатлалаас хуулагдана)
    albn_tushaal    TEXT,                     -- Албан тушаал (шатлалаас хуулагдана)
    tsalin          INTEGER,                  -- Цалингийн дүн (шатлалаас хуулагдана)
    status          TEXT NOT NULL DEFAULT 'хүлээгдэж буй',  -- хүлээгдэж буй / зөвшөөрсөн / татгалзсан
    request_date    TEXT,                     -- Хүсэлт гаргасан огноо (YYYY-MM-DD)
    note            TEXT,                     -- Тайлбар (сонголтоор)
    FOREIGN KEY (member_id) REFERENCES member(id) ON DELETE CASCADE,
    FOREIGN KEY (salary_scale_id) REFERENCES salary_scale(id) ON DELETE SET NULL
);

-- Гишүүний боловсрол (нэг гишүүнд олон мөр). education_degree-г лавлахаас сонгоно.
CREATE TABLE IF NOT EXISTS member_education (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id           INTEGER NOT NULL,    -- Аль гишүүний боловсрол
    education_degree_id INTEGER,             -- Боловсролын зэрэг (FK, лавлах)
    surguuli            TEXT,                -- Сургууль
    mergejil            TEXT,                -- Мэргэжил
    tugssun_on          TEXT,               -- Төгссөн он
    FOREIGN KEY (member_id) REFERENCES member(id) ON DELETE CASCADE,
    FOREIGN KEY (education_degree_id) REFERENCES education_degree(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_horoo_holboo ON horoo(holboo_id);
CREATE INDEX IF NOT EXISTS idx_org_horoo ON organization(horoo_id);
CREATE INDEX IF NOT EXISTS idx_member_org ON member(organization_id);
CREATE INDEX IF NOT EXISTS idx_contact_owner ON contact(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_salreq_member ON salary_request(member_id);
CREATE INDEX IF NOT EXISTS idx_medu_member ON member_education(member_id);
"""

# ------------------------- Лавлах хүснэгтүүд (reference) -------------------------
# school_category — Боловсролын байгууллагын ангилал (бие даасан лавлах).
SCHEMA_REF = """
CREATE TABLE IF NOT EXISTS school_category (
    id        INTEGER PRIMARY KEY,
    buten_ner TEXT NOT NULL,   -- Бүтэн нэр
    tovch_ner TEXT,            -- Товчилсон нэр (СӨБ, ЕБС ...)
    angli_ner TEXT             -- Англи нэр
);

CREATE TABLE IF NOT EXISTS education_degree (
    id  INTEGER PRIMARY KEY,
    ner TEXT NOT NULL          -- Боловсролын зэрэг
);
"""

# Сургуулийн ангиллын анхдагч өгөгдөл (Ангилал сургуулиуд.xlsx-аас)
SCHOOL_CATEGORIES = [
    (1, "Сургуулийн өмнөх боловсрол", "СӨБ", "Early Childhood Education (Preschool)"),
    (2, "Ерөнхий боловсрол", "ЕБС", "General Education (Primary and Secondary Education)"),
    (3, "Мэргэжлийн боловсрол, сургалт", "МБС", "Technical and Vocational Education and Training (TVET)"),
    (4, "Их, дээд боловсрол", "ИДС", "Higher Education (Universities and Colleges)"),
    (5, "Шинжлэх ухаан", "ШУ", "Science / Research"),
    (6, "Боловсрол, шинжлэх ухааны туслах үйлчилгээ", "БШУТҮ", "Support Services in Education and Science"),
    (7, "Нэмэлт боловсрол", None, None),
]

# Боловсролын зэргийн ангилал (Боловсролын зэргийн ангилал.xlsx-аас)
EDUCATION_DEGREES = [
    (1, "Доктор, Профессор"),
    (2, "Профессор"),
    (3, "Дэд профессор"),
    (4, "Магистр, Доктор"),
    (5, "Магистр"),
    (6, "Доктор (PhD)"),
    (7, "Доктор (ScD)"),
    (8, "Бакалавр + Магистр"),
    (9, "Бакалавр (суурь)"),
    (10, "Дэд бакалавр"),
    (11, "Бакалавр (явц)"),
    (12, "Мэргэжлийн боловсрол (МБС)"),
    (13, "Техникийн боловсрол"),
    (14, "Бүрэн дунд"),
    (15, "Тусгай дунд"),
    (16, "Бага боловсрол"),
]

# Цалингийн шатлалын анхдагч өгөгдөл (tsalin_husnegt.xlsx-аас): (salbar, kod, albn_tushaal, tsalin)
SALARY_SCALE = [
    ("СӨБ ба ЕБС", "ТҮБД-5", "Захирал, эрхлэгч", 3093930),
    ("СӨБ ба ЕБС", "ТҮБД-4", "Менежер, ЕБС-ийн багш", 2946510),
    ("СӨБ ба ЕБС", "ТҮБД-3", "Бага, дунд, ахлах ангийн багш, хоол зүйч", 2804760),
    ("СӨБ ба ЕБС", "ТҮБД-2", "Дотуур байрны багш", 2672460),
    ("СӨБ ба ЕБС", "ТҮБД-1", "Туслах багш", 2424870),
    ("Мэргэжлийн боловсрол", "ТҮМБ-6", "Захирал", 1718000),
    ("Мэргэжлийн боловсрол", "ТҮМБ-5", "Менежер", 1637000),
    ("Мэргэжлийн боловсрол", "ТҮМБ-4", "Багш, аргазүйч, нийгмийн ажилтан", 1559000),
    ("Мэргэжлийн боловсрол", "ТҮМБ-3", "Ерөнхий эрдмийн багш, хоол зүйч", 1484000),
    ("Мэргэжлийн боловсрол", "ТҮМБ-2", "Дотуур байрны багш", 1414000),
    ("Мэргэжлийн боловсрол", "ТҮМБ-1", "Дадлагажигч багш", 1283000),
    ("Шинжлэх ухаан", "ТҮШУУ-7", "Академийн ерөнхийлөгч", 2388000),
    ("Шинжлэх ухаан", "ТҮШУУ-6", "Дэд ерөнхийлөгч, нарийн бичиг", 1805000),
    ("Шинжлэх ухаан", "ТҮШУУ-5", "Захирал, дэд захирал", 1718000),
    ("Шинжлэх ухаан", "ТҮШУУ-4", "Нэгжийн дарга", 1637000),
    ("Шинжлэх ухаан", "ТҮШУУ-3", "Судлаач, мэргэжилтэн", 1559000),
    ("Шинжлэх ухаан", "ТҮШУУ-2", "Ажилтан", 1484000),
    ("Шинжлэх ухаан", "ТҮШУУ-1", "Туслах ажилтан", 1283000),
]


def get_db():
    """Мөр бүрийг dict шиг хандах боломжтой холболт буцаана."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Хуучин DB дээр CREATE TABLE IF NOT EXISTS ажиллахгүй тул дутуу баганыг нэмнэ.
# {хүснэгт: [(багана, тодорхойлолт), ...]}
_MIGRATIONS = {
    "member": [
        ("register_number", "TEXT"),
        ("ue_batlamj_number", "TEXT"),
        ("ue_joined_date", "TEXT"),
        ("member_status", "TEXT"),
        ("albn_tushaal", "TEXT"),
        ("mergejil", "TEXT"),
        ("bolovsrol", "TEXT"),
        ("phone_fax", "TEXT"),
        ("address", "TEXT"),
        ("signature", "INTEGER DEFAULT 0"),
    ],
    "salary_request": [
        ("salary_scale_id", "INTEGER"),
    ],
}


def _migrate(conn):
    for table, cols in _MIGRATIONS.items():
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols:
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.executescript(SCHEMA_UNION)
    conn.executescript(SCHEMA_REF)
    _migrate(conn)
    conn.commit()
    conn.close()


def seed_education_degree():
    """Боловсролын зэргийн ангиллын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO education_degree(id, ner) VALUES (?, ?)",
        EDUCATION_DEGREES,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM education_degree").fetchone()[0]
    conn.close()
    print("Боловсролын зэрэг ачаалагдлаа:", n)


def seed_salary_scale():
    """Цалингийн шатлалын лавлах өгөгдлийг ачаална (kod-оор давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO salary_scale(salbar, kod, albn_tushaal, tsalin) "
        "VALUES (?, ?, ?, ?)",
        SALARY_SCALE,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM salary_scale").fetchone()[0]
    conn.close()
    print("Цалингийн шатлал ачаалагдлаа:", n)


def seed_school_category():
    """Сургуулийн ангиллын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO school_category(id, buten_ner, tovch_ner, angli_ner) "
        "VALUES (?, ?, ?, ?)",
        SCHOOL_CATEGORIES,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM school_category").fetchone()[0]
    conn.close()
    print("Сургуулийн ангилал ачаалагдлаа:", n)


def _load_json(name):
    with open(os.path.join(BASE_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def seed():
    """JSON файлуудаас өгөгдлийг хүснэгтэд ачаална (давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    cur = conn.cursor()

    au1 = _load_json("admin_unit1.json")
    cur.executemany(
        "INSERT OR IGNORE INTO admin_unit1(code, name) VALUES (?, ?)",
        [(r["code"], r["name"]) for r in au1],
    )

    au2 = _load_json("admin_unit2.json")
    cur.executemany(
        "INSERT OR IGNORE INTO admin_unit2(au2_code, au2_name, au1_code) VALUES (?, ?, ?)",
        [(r["au2_code"], r["au2_name"], r["au1_code"]) for r in au2],
    )

    au3 = _load_json("admin_unit3.json")
    # Зарим au3 мөрийн au2_code эх хүснэгтэд байхгүй байж болзошгүй тул шүүнэ.
    valid_au2 = {r["au2_code"] for r in au2}
    rows3 = [
        (r["au3_code"], r["au3_name"], r["au1_code"], r["au2_code"])
        for r in au3
        if r["au2_code"] in valid_au2
    ]
    skipped = len(au3) - len(rows3)
    cur.executemany(
        "INSERT OR IGNORE INTO admin_unit3"
        "(au3_code, au3_name, au1_code, au2_code) VALUES (?, ?, ?, ?)",
        rows3,
    )

    conn.commit()
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("admin_unit1", "admin_unit2", "admin_unit3")
    }
    conn.close()
    print("Ачаалал дууслаа:", counts, "| алгассан au3:", skipped)


def seed_union():
    """Үйлдвэрчний эвлэлийн бүтцэд жишээ өгөгдөл нэмнэ (хоосон үед л)."""
    init_db()
    conn = get_db()
    cur = conn.cursor()
    if cur.execute("SELECT COUNT(*) FROM holboo").fetchone()[0] > 0:
        conn.close()
        print("Union өгөгдөл аль хэдийн орсон байна — алгаслаа.")
        return

    cur.execute("INSERT INTO holboo(name) VALUES (?)",
                ("Боловсрол, шинжлэх ухааны үйлдвэрчний эвлэлийн холбоо",))
    holboo_id = cur.lastrowid

    cur.execute("INSERT INTO horoo(holboo_id, name) VALUES (?, ?)",
                (holboo_id, "Сүхбаатар дүүргийн хороо"))
    horoo_id = cur.lastrowid

    cur.execute(
        """INSERT INTO organization
           (horoo_id, name, org_type, school_type, registration_number,
            founded_date, activity_code, activity_name, parent_org, address)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (horoo_id, "АШУҮИС-ийн харьяа сургууль", "Сургууль", "Их сургууль",
         "9923659", "2023-01-31", "8530", "Дээд боловсрол олгох үйл ажиллагаа",
         "Анагаахын шинжлэх ухааны үндэсний их сургууль", "Ард Аюушийн гудамж"),
    )
    org_id = cur.lastrowid

    cur.executemany(
        "INSERT INTO member(organization_id, name, gender, birth_date) VALUES (?,?,?,?)",
        [
            (org_id, "Болд", "эр", "1980-05-10"),
            (org_id, "Сараа", "эм", "1995-09-20"),
            (org_id, "Дулмаа", "эм", "2000-03-15"),
            (org_id, "Ганбат", "эр", "1975-12-01"),
        ],
    )

    cur.executemany(
        "INSERT INTO contact(owner_type, owner_id, type, value, note) VALUES (?,?,?,?,?)",
        [
            ("horoo", horoo_id, "утас", "99112233", "захиргаа"),
            ("horoo", horoo_id, "и-мэйл", "horoo@example.mn", None),
            ("organization", org_id, "утас", "70112233", "нягтлан"),
            ("organization", org_id, "факс", "70112234", None),
            ("organization", org_id, "и-мэйл", "info@example.mn", None),
        ],
    )

    conn.commit()
    conn.close()
    print("Union жишээ өгөгдөл нэмэгдлээ.")


if __name__ == "__main__":
    seed()
    seed_union()
    seed_school_category()
    seed_salary_scale()
    seed_education_degree()
