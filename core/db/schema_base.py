"""Схем: засаг захиргааны нэгж (SCHEMA) ба үйлдвэрчний эвлэлийн бүтэц (SCHEMA_UNION)."""


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
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    holboo_id           INTEGER NOT NULL,    -- Аль холбоонд харьяалагдах
    name                TEXT NOT NULL,       -- Хорооны нэр
    type                TEXT,               -- Төрөл
    registration_number TEXT,               -- Регистрийн дугаар (РД)
    founded_date        TEXT,               -- Байгуулагдсан огноо (YYYY-MM-DD)
    FOREIGN KEY (holboo_id) REFERENCES holboo(id) ON DELETE CASCADE
);

-- Гишүүн байгууллага. ХОРООНД ХАРЬЯАЛАГДАХГҮЙ (horoo_id хасагдсан) —
-- байгууллага бие даан бүртгэгдэж, гишүүд нь organization_id-аар холбогдоно.
CREATE TABLE IF NOT EXISTS organization (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,       -- Байгууллагын нэр
    school_category_id  INTEGER,            -- Сургуулийн ангилал (school_category.id) = 2 орон
    org_code            TEXT,               -- Байгууллагын 3 оронтой код (гараас)
    -- Ангилал(2) + org_code(3) = байгууллагын 5 оронтой код. Хадгалахгүй, уншихад
    -- printf('%02d', school_category_id) || org_code гэж бодогдоно (client/union.py).
    registration_number TEXT,               -- Регистрийн дугаар
    state_reg_number    TEXT,               -- Улсын бүртгэлийн дугаар
    founded_date        TEXT,               -- Үүсгэн байгуулагдсан огноо (YYYY-MM-DD)
    activity_code       TEXT,               -- Үйл ажиллагааны чиглэлийн код
    activity_name       TEXT,               -- Үндсэн үйл ажиллагааны чиглэл
    parent_org          TEXT,               -- Толгой байгууллага
    au1_code            TEXT,               -- Аймаг/нийслэл (admin_unit1.code)
    au2_code            TEXT,               -- Сум/дүүрэг (admin_unit2.au2_code)
    au3_code            TEXT,               -- Баг/хороо (admin_unit3.au3_code)
    address_detail      TEXT,               -- Дэлгэрэнгүй хаяг
    postal_address      TEXT,               -- Шуудангийн хаяг
    -- Байгууллагын үндсэн холбоо барих мэдээлэл (маягтад шууд дүүргэхэд зориулсан).
    -- Үүнээс ИЛҮҮ олон утас/факс/и-мэйл хэрэгтэй бол contact хүснэгтийг ашиглана.
    phone1              TEXT,               -- Утас 1
    phone2              TEXT,               -- Утас 2
    email               TEXT,               -- И-мэйл
    contact_name        TEXT,               -- Холбогдох хүний нэр
    structure_id        INTEGER,            -- Бүтцийн удирдлага (structure.id)
    FOREIGN KEY (school_category_id) REFERENCES school_category(id) ON DELETE SET NULL,
    FOREIGN KEY (structure_id) REFERENCES structure(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS member (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id   INTEGER NOT NULL,      -- Аль гишүүн байгууллагад харьяалагдах (FK)
    last_name         TEXT,                  -- 1. Овог
    first_name        TEXT NOT NULL,         -- 1. Нэр
    birth_date        TEXT,                  -- 2. Төрсөн он (YYYY-MM-DD)
    gender            TEXT,                  -- 3. Хүйс ('эр' / 'эм')
    register_number   TEXT,                  -- 4. Регистрийн дугаар
    union_card_code   TEXT,                  -- 5а. Гараас авах 4 оронтой код
    -- 5. ҮЭ-ийн батламжийн 9 оронтой дугаар. Гараар бичихгүй — байгууллагын
    --    5 оронтой код + union_card_code(4) хосолж автоматаар бүрдэнэ.
    union_card_number TEXT,
    union_joined_date TEXT,                  -- 6. ҮЭ-д элссэн он сар өдөр (YYYY-MM-DD)
    member_status     TEXT,                  -- 7. ҮЭ-ийн гишүүний статус
    status            TEXT,                  -- Бүртгэлийн төлөв (чөлөөт текст)
    position_id       INTEGER,               -- 8. Албан тушаал (position.id)
    profession_id     INTEGER,               -- 9. Мэргэжил (profession.id)
    salary_scale_id   INTEGER,               -- Цалингийн шатлал (salary_scale.id)
    email             TEXT,                  -- И-мэйл
    au1_code          TEXT,                  -- Аймаг/нийслэл (admin_unit1.code)
    au2_code          TEXT,                  -- Сум/дүүрэг (admin_unit2.au2_code)
    au3_code          TEXT,                  -- Баг/хороо (admin_unit3.au3_code)
    address_detail    TEXT,                  -- 12. Оршин суугаа дэлгэрэнгүй хаяг
    signature         INTEGER DEFAULT 0,     -- Гарын үсэг байгаа эсэх (0/1)
    is_active         INTEGER DEFAULT 1,     -- Идэвхтэй гишүүн эсэх (0/1)
    FOREIGN KEY (organization_id) REFERENCES organization(id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES position(id) ON DELETE SET NULL,
    FOREIGN KEY (profession_id) REFERENCES profession(id) ON DELETE SET NULL,
    FOREIGN KEY (salary_scale_id) REFERENCES salary_scale(id) ON DELETE SET NULL
);
-- Боловсрол (#10) нь member_education хүснэгтэд олноор бүртгэгдэнэ.
-- Утас/факс (#11) нь contact хүснэгтэд олноор бүртгэгдэнэ (owner_type='member').

CREATE TABLE IF NOT EXISTS contact (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_type TEXT NOT NULL,                -- 'horoo' / 'organization' / 'member'
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

-- Гишүүний шагнал, урамшуулал (нэг гишүүнд ОЛОН мөр). Төрлийг reward_type лавлахаас сонгоно.
CREATE TABLE IF NOT EXISTS member_reward (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id      INTEGER NOT NULL,    -- Аль гишүүний шагнал
    reward_type_id INTEGER,             -- Шагнал, урамшууллын төрөл (FK, лавлах)
    description    TEXT,                -- Тайлбар (шагналын дэлгэрэнгүй)
    reward_date    TEXT,                -- Шагнасан огноо (YYYY-MM-DD)
    FOREIGN KEY (member_id) REFERENCES member(id) ON DELETE CASCADE,
    FOREIGN KEY (reward_type_id) REFERENCES reward_type(id) ON DELETE SET NULL
);

-- Гишүүний хавсаргасан файл (батламж г.м.) — зөвхөн PDF, нэг гишүүнд ОЛОН файл.
-- Файлын агуулга нь диск дээр (uploads/member/), энд зөвхөн мэдээлэл нь хадгалагдана.
CREATE TABLE IF NOT EXISTS member_file (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL,       -- Аль гишүүний файл
    file_name   TEXT NOT NULL,          -- Хэрэглэгчийн оруулсан анхны нэр
    stored_name TEXT NOT NULL UNIQUE,   -- Диск дээрх нэр (давхцахгүй, uuid.pdf)
    size        INTEGER,                -- Хэмжээ (байт)
    note        TEXT,                   -- Тайлбар (ж: "ҮЭ-ийн батламж")
    uploaded_at TEXT,                   -- Оруулсан огноо (ISO)
    FOREIGN KEY (member_id) REFERENCES member(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_horoo_holboo ON horoo(holboo_id);
CREATE INDEX IF NOT EXISTS idx_member_org ON member(organization_id);
CREATE INDEX IF NOT EXISTS idx_contact_owner ON contact(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_salreq_member ON salary_request(member_id);
CREATE INDEX IF NOT EXISTS idx_medu_member ON member_education(member_id);
CREATE INDEX IF NOT EXISTS idx_mfile_member ON member_file(member_id);
CREATE INDEX IF NOT EXISTS idx_mreward_member ON member_reward(member_id);
"""
