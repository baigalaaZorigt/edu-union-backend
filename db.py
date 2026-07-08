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
    school_type         TEXT,               -- Их сургууль / СӨБ / ЕБС / МСҮТ
    registration_number TEXT,               -- Регистрийн дугаар
    founded_date        TEXT,               -- Үүсгэн байгуулагдсан огноо (YYYY-MM-DD)
    activity_code       TEXT,               -- Үйл ажиллагааны чиглэлийн код
    activity_name       TEXT,               -- Үндсэн үйл ажиллагааны чиглэл
    parent_org          TEXT,               -- Толгой байгууллага
    au1_code            TEXT,               -- Аймаг/нийслэл (admin_unit1.code)
    au2_code            TEXT,               -- Сум/дүүрэг (admin_unit2.au2_code)
    au3_code            TEXT,               -- Баг/хороо (admin_unit3.au3_code)
    address_detail      TEXT,               -- Дэлгэрэнгүй хаяг
    FOREIGN KEY (horoo_id) REFERENCES horoo(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS member (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id   INTEGER NOT NULL,      -- Аль гишүүн байгууллагад харьяалагдах (FK)
    name              TEXT NOT NULL,         -- 1. Овог нэр
    birth_date        TEXT,                  -- 2. Төрсөн он (YYYY-MM-DD)
    gender            TEXT,                  -- 3. Хүйс ('эр' / 'эм')
    register_number   TEXT,                  -- 4. Регистрийн дугаар
    union_card_number TEXT,                  -- 5. ҮЭ-ийн батламжийн дугаар
    union_joined_date TEXT,                  -- 6. ҮЭ-д элссэн он сар өдөр (YYYY-MM-DD)
    member_status     TEXT,                  -- 7. ҮЭ-ийн гишүүний статус
    position          TEXT,                  -- 8. Эрхэлж байгаа ажил, албан тушаал
    profession        TEXT,                  -- 9. Мэргэжил
    phone_fax         TEXT,                  -- 11. Факс, утасны дугаарууд
    au1_code          TEXT,                  -- Аймаг/нийслэл (admin_unit1.code)
    au2_code          TEXT,                  -- Сум/дүүрэг (admin_unit2.au2_code)
    au3_code          TEXT,                  -- Баг/хороо (admin_unit3.au3_code)
    address_detail    TEXT,                  -- 12. Оршин суугаа дэлгэрэнгүй хаяг
    signature         INTEGER DEFAULT 0,     -- Гарын үсэг байгаа эсэх (0/1)
    FOREIGN KEY (organization_id) REFERENCES organization(id) ON DELETE CASCADE
);
-- Боловсрол (#10) нь member_education хүснэгтэд олноор бүртгэгдэнэ.

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
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sector   TEXT NOT NULL,               -- Салбар
    code     TEXT NOT NULL UNIQUE,        -- Код (ТҮБД-5 гэх мэт)
    position TEXT,                        -- Албан тушаал
    salary   INTEGER                      -- Цалин (төгрөг)
);

CREATE TABLE IF NOT EXISTS salary_request (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id       INTEGER NOT NULL,         -- Аль гишүүний цалингийн хүсэлт
    salary_scale_id INTEGER,                  -- Сонгосон цалингийн шатлал (FK, snapshot хийгдэнэ)
    sector          TEXT,                     -- Салбар (шатлалаас хуулагдана)
    code            TEXT,                     -- Код (шатлалаас хуулагдана)
    position        TEXT,                     -- Албан тушаал (шатлалаас хуулагдана)
    salary          INTEGER,                  -- Цалингийн дүн (шатлалаас хуулагдана)
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
    school              TEXT,                -- Сургууль
    profession          TEXT,                -- Мэргэжил
    graduation_year     TEXT,               -- Төгссөн он
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

# ------------------------- Хэрэглэгчийн удирдлага (user management) -------------------------
# permission (Эрх) — CRUD үйлдэл бүр нэг эрх (ж: 'user.create').
# role (Дүр) нь role_permission-оор дамжуулан ОЛОН эрхтэй (M:N).
# app_user (Хэрэглэгч) нь role_id-аар нэг дүр СОНГОЖ авах ба дүрийнхээ бүх эрхийг удамшуулна.
SCHEMA_USER = """
CREATE TABLE IF NOT EXISTS permission (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,   -- нөөц.үйлдэл, ж: 'user.create'
    name        TEXT NOT NULL,          -- Хүн уншихуйц нэр
    resource    TEXT,                   -- Нөөц (user, role, member ...)
    action      TEXT,                   -- create / read / update / delete
    description TEXT                     -- Тайлбар (сонголтоор)
);

CREATE TABLE IF NOT EXISTS role (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,   -- Дүрийн нэр (admin, manager ...)
    description TEXT                     -- Тайлбар
);

CREATE TABLE IF NOT EXISTS role_permission (
    role_id       INTEGER NOT NULL,     -- Аль дүр
    permission_id INTEGER NOT NULL,     -- Аль эрх
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permission(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_user (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE, -- Нэвтрэх нэр
    password_hash TEXT NOT NULL,        -- Нууц үгийн hash (энгийн текстээр хадгалахгүй)
    full_name     TEXT,                 -- Овог нэр
    email         TEXT,                 -- И-мэйл
    role_id       INTEGER,              -- Сонгосон дүр (FK) — эндээс эрхээ авна
    is_active     INTEGER DEFAULT 1,    -- Идэвхтэй эсэх (0/1)
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_rp_role ON role_permission(role_id);
CREATE INDEX IF NOT EXISTS idx_rp_perm ON role_permission(permission_id);
CREATE INDEX IF NOT EXISTS idx_user_role ON app_user(role_id);
"""

# ------------------------- Лавлах хүснэгтүүд (reference) -------------------------
# school_category — Боловсролын байгууллагын ангилал (бие даасан лавлах).
SCHEMA_REF = """
CREATE TABLE IF NOT EXISTS school_category (
    id           INTEGER PRIMARY KEY,
    full_name    TEXT NOT NULL,   -- Бүтэн нэр
    short_name   TEXT,            -- Товчилсон нэр (СӨБ, ЕБС ...)
    english_name TEXT             -- Англи нэр
);

CREATE TABLE IF NOT EXISTS education_degree (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL          -- Боловсролын зэрэг
);

CREATE TABLE IF NOT EXISTS position (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL          -- Албан тушаал
);

CREATE TABLE IF NOT EXISTS profession (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL          -- Мэргэжил
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

# Албан тушаалын лавлах (боловсролын байгууллагын нийтлэг албан тушаалууд)
POSITIONS = [
    (1, "Захирал"),
    (2, "Дэд захирал"),
    (3, "Сургалтын менежер"),
    (4, "Эрхлэгч"),
    (5, "Ахлах багш"),
    (6, "Багш"),
    (7, "Дадлагажигч багш"),
    (8, "Туслах багш"),
    (9, "Нийгмийн ажилтан"),
    (10, "Сэтгэл зүйч"),
    (11, "Номын санч"),
    (12, "Лаборант"),
    (13, "Эмч"),
    (14, "Сувилагч"),
    (15, "Нягтлан бодогч"),
    (16, "Нярав"),
    (17, "Бичиг хэргийн ажилтан"),
    (18, "Хүний нөөцийн мэргэжилтэн"),
    (19, "Мэдээллийн технологийн мэргэжилтэн"),
    (20, "Үйлчлэгч"),
]

# Мэргэжлийн лавлах (боловсролын салбарын нийтлэг мэргэжлүүд)
PROFESSIONS = [
    (1, "Бага ангийн багш"),
    (2, "Математикийн багш"),
    (3, "Физикийн багш"),
    (4, "Химийн багш"),
    (5, "Биологийн багш"),
    (6, "Монгол хэл, уран зохиолын багш"),
    (7, "Англи хэлний багш"),
    (8, "Орос хэлний багш"),
    (9, "Түүхийн багш"),
    (10, "Газарзүйн багш"),
    (11, "Мэдээллийн технологийн багш"),
    (12, "Биеийн тамирын багш"),
    (13, "Дуу хөгжмийн багш"),
    (14, "Дүрслэх урлагийн багш"),
    (15, "Цэцэрлэгийн багш"),
    (16, "Нийгмийн ухааны багш"),
    (17, "Эдийн засагч"),
    (18, "Нягтлан бодогч"),
    (19, "Инженер"),
    (20, "Эмч"),
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


# Эрх үүсгэх нөөцүүд ба үйлдлүүд — эдгээрийн үржвэрээр CRUD эрхүүд seed хийгдэнэ.
PERMISSION_RESOURCES = [
    ("user", "Хэрэглэгч"),
    ("role", "Дүр"),
    ("permission", "Эрх"),
    ("admin_unit", "Засаг захиргааны нэгж"),
    ("holboo", "Холбоо"),
    ("horoo", "Хороо"),
    ("organization", "Байгууллага"),
    ("member", "Гишүүн"),
    ("salary_request", "Цалингийн хүсэлт"),
    ("salary_scale", "Цалингийн шатлал"),
]
PERMISSION_ACTIONS = [
    ("create", "нэмэх"),
    ("read", "харах"),
    ("update", "засах"),
    ("delete", "устгах"),
]

# Анхдагч дүрүүд (нэр, тайлбар)
DEFAULT_ROLES = [
    ("admin", "Бүх эрхтэй систем администратор"),
    ("manager", "Үйл ажиллагаа хариуцсан менежер"),
    ("viewer", "Зөвхөн харах эрхтэй хэрэглэгч"),
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
        ("union_card_number", "TEXT"),
        ("union_joined_date", "TEXT"),
        ("member_status", "TEXT"),
        ("position", "TEXT"),
        ("profession", "TEXT"),
        ("phone_fax", "TEXT"),
        ("au1_code", "TEXT"),
        ("au2_code", "TEXT"),
        ("au3_code", "TEXT"),
        ("signature", "INTEGER DEFAULT 0"),
    ],
    "salary_request": [
        ("salary_scale_id", "INTEGER"),
    ],
    "organization": [
        ("au1_code", "TEXT"),
        ("au2_code", "TEXT"),
        ("au3_code", "TEXT"),
    ],
}

# Хуучин галиглал баганыг англи нэр рүү шилжүүлэх: хүснэгт -> [(хуучин, шинэ), ...]
_RENAME_COLUMNS = {
    "salary_scale": [("salbar", "sector"), ("kod", "code"),
                     ("albn_tushaal", "position"), ("tsalin", "salary")],
    "salary_request": [("salbar", "sector"), ("kod", "code"),
                       ("albn_tushaal", "position"), ("tsalin", "salary")],
    "member": [("albn_tushaal", "position"), ("mergejil", "profession"),
               ("ue_batlamj_number", "union_card_number"),
               ("ue_joined_date", "union_joined_date")],
    "member_education": [("surguuli", "school"), ("mergejil", "profession"),
                         ("tugssun_on", "graduation_year")],
    "education_degree": [("ner", "name")],
    "school_category": [("buten_ner", "full_name"), ("tovch_ner", "short_name"),
                        ("angli_ner", "english_name")],
}

# Устгах баганууд (хэрэв байгаа бол): хүснэгт -> [багана, ...]
_DROP_COLUMNS = {
    "organization": ["org_type"],
    "member": ["bolovsrol"],
}


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


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
        elif "address_detail" not in _cols(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN address_detail TEXT")
    # 3) Хэрэглэхгүй болсон баганыг устгах
    for table, drops in _DROP_COLUMNS.items():
        existing = _cols(conn, table)
        for name in drops:
            if name in existing:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {name}")


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.executescript(SCHEMA_UNION)
    conn.executescript(SCHEMA_REF)
    conn.executescript(SCHEMA_USER)
    _migrate(conn)
    conn.commit()
    conn.close()


def seed_education_degree():
    """Боловсролын зэргийн ангиллын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO education_degree(id, name) VALUES (?, ?)",
        EDUCATION_DEGREES,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM education_degree").fetchone()[0]
    conn.close()
    print("Боловсролын зэрэг ачаалагдлаа:", n)


def seed_position():
    """Албан тушаалын лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO position(id, name) VALUES (?, ?)", POSITIONS)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM position").fetchone()[0]
    conn.close()
    print("Албан тушаал ачаалагдлаа:", n)


def seed_profession():
    """Мэргэжлийн лавлах өгөгдлийг ачаална (давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO profession(id, name) VALUES (?, ?)", PROFESSIONS)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM profession").fetchone()[0]
    conn.close()
    print("Мэргэжил ачаалагдлаа:", n)


def seed_salary_scale():
    """Цалингийн шатлалын лавлах өгөгдлийг ачаална (kod-оор давхардлыг алгасна)."""
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO salary_scale(sector, code, position, salary) "
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
        "INSERT OR IGNORE INTO school_category(id, full_name, short_name, english_name) "
        "VALUES (?, ?, ?, ?)",
        SCHOOL_CATEGORIES,
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM school_category").fetchone()[0]
    conn.close()
    print("Сургуулийн ангилал ачаалагдлаа:", n)


def seed_users():
    """Хэрэглэгчийн удирдлагын seed: CRUD эрхүүд, анхдагч дүрүүд, admin хэрэглэгч.

    - permission: нөөц × үйлдэл бүрээр (INSERT OR IGNORE — давхардлыг алгасна)
    - role: admin / manager / viewer
    - role_permission: admin→бүх, viewer→бүх read, manager→үйл ажиллагааны CRUD
    - app_user: анхны 'admin' хэрэглэгч (app_user хоосон үед л)
    """
    init_db()
    conn = get_db()
    cur = conn.cursor()

    # 1) Эрхүүд (нөөц × үйлдэл)
    perms = [
        (f"{res}.{act}", f"{res_label} {act_label}", res, act)
        for res, res_label in PERMISSION_RESOURCES
        for act, act_label in PERMISSION_ACTIONS
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO permission(code, name, resource, action) VALUES (?,?,?,?)",
        perms,
    )

    # 2) Дүрүүд
    cur.executemany(
        "INSERT OR IGNORE INTO role(name, description) VALUES (?, ?)", DEFAULT_ROLES)
    conn.commit()

    def role_id(name):
        return cur.execute("SELECT id FROM role WHERE name=?", (name,)).fetchone()[0]

    def assign(role_name, where_sql, params=()):
        """Тухайн дүрд WHERE нөхцөлд тохирох бүх эрхийг оноож (давхардлыг алгасна)."""
        cur.execute(
            "INSERT OR IGNORE INTO role_permission(role_id, permission_id) "
            f"SELECT ?, id FROM permission WHERE {where_sql}",
            (role_id(role_name), *params),
        )

    # 3) Эрх оноох
    assign("admin", "1=1")                       # бүх эрх
    assign("viewer", "action = 'read'")          # зөвхөн харах
    assign(                                       # менежер: үйл ажиллагааны CRUD
        "manager",
        "action IN ('create','read','update') AND resource IN "
        "('holboo','horoo','organization','member','salary_request','salary_scale')",
    )
    conn.commit()

    # 4) Анхны admin хэрэглэгч (зөвхөн хэрэглэгч огт байхгүй үед)
    if cur.execute("SELECT COUNT(*) FROM app_user").fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash
        cur.execute(
            "INSERT INTO app_user(username, password_hash, full_name, role_id, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            ("admin", generate_password_hash("admin123", method="pbkdf2"),
             "Систем администратор", role_id("admin")),
        )
        conn.commit()
        print("Анхны хэрэглэгч үүслээ: admin / admin123 (нэвтэрсний дараа нууц үгээ солино уу)")

    n_perm = cur.execute("SELECT COUNT(*) FROM permission").fetchone()[0]
    n_role = cur.execute("SELECT COUNT(*) FROM role").fetchone()[0]
    conn.close()
    print(f"User management seed дууслаа: {n_perm} эрх, {n_role} дүр.")


def _load_json(name):
    # Seed JSON файлууд data/seed/ дотор байрлана.
    with open(os.path.join(BASE_DIR, "data", "seed", name), encoding="utf-8") as f:
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
           (horoo_id, name, school_type, registration_number,
            founded_date, activity_code, activity_name, parent_org,
            au1_code, au2_code, address_detail)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (horoo_id, "АШУҮИС-ийн харьяа сургууль", "Их сургууль",
         "9923659", "2023-01-31", "8530", "Дээд боловсрол олгох үйл ажиллагаа",
         "Анагаахын шинжлэх ухааны үндэсний их сургууль",
         "011", "01101", "Ард Аюушийн гудамж"),
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


def seed_all():
    """Бүх домэйны seed-г дараалан ажиллуулна (`python db.py` үүнийг дуудна)."""
    seed()
    seed_union()
    seed_school_category()
    seed_salary_scale()
    seed_education_degree()
    seed_position()
    seed_profession()
    seed_users()


def ensure_seeded():
    """Хоосон хүснэгтүүдийг л автоматаар seed хийнэ. Idempotent.

    create_app() (run.py) эндээс дуудна — Render/Heroku зэрэг `python db.py`-г
    тусад нь ажиллуулдаггүй орчинд өгөгдөл (ж: эрхийн жагсаалт) хоосон үлдэхээс
    сэргийлнэ. Аль хэдийн seed хийсэн бол зөвхөн COUNT шалгаад өнгөрнө.
    """
    init_db()
    conn = get_db()

    def empty(table):
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

    need_units = empty("admin_unit1")
    need_ref = (empty("school_category") or empty("education_degree")
                or empty("salary_scale") or empty("position") or empty("profession"))
    need_users = empty("permission")
    conn.close()

    if need_units:
        seed()
        seed_union()
    if need_ref:
        seed_school_category()
        seed_salary_scale()
        seed_education_degree()
        seed_position()
        seed_profession()
    if need_users:
        seed_users()


if __name__ == "__main__":
    seed_all()
