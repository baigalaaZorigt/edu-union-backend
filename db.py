"""SQLite холболт ба бүтэц (schema) үүсгэх, JSON өгөгдлийг ачаалах."""
import json
import os
import sqlite3
from datetime import datetime, timezone

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
    last_name     TEXT,                 -- Овог
    first_name    TEXT,                 -- Нэр
    email         TEXT,                 -- И-мэйл
    role_id       INTEGER,              -- Сонгосон дүр (FK) — эндээс эрхээ авна
    structure_id  INTEGER,              -- Бүтцийн удирдлага (structure.id)
    is_active     INTEGER DEFAULT 1,    -- Идэвхтэй эсэх (0/1)
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE SET NULL,
    FOREIGN KEY (structure_id) REFERENCES structure(id) ON DELETE SET NULL
);

-- Хэрэглэгчийн ХАМРАХ ХҮРЭЭ (user_scope) — user_scope_api_spec.md.
-- Дүр нь "юу хийж болох"-ыг заадаг бол энэ нь "АЛЬ өгөгдлийг харах"-ыг заана.
-- Нэг хэрэглэгчид НЭГ мөр (user_id нь PRIMARY KEY тул 1:1).
--   Зөвлөх/Мэргэжилтэн: school_type + (rural бол organization_ids, эс бөгөөс
--                       district_au2_code)
--   Сургуулийн менежер: organization_id (яг нэг сургууль)
CREATE TABLE IF NOT EXISTS user_scope (
    user_id           INTEGER PRIMARY KEY,   -- Аль хэрэглэгч (1:1)
    school_type       TEXT,                  -- general/preschool/higher/vocational/science/rural
    district_au2_code TEXT,                  -- УБ-ын дүүрэг (admin_unit2.au2_code)
    organization_ids  TEXT DEFAULT '[]',     -- JSON массив (зөвхөн school_type='rural')
    organization_id   INTEGER,               -- Менежерийн харьяалагдах ганц сургууль
    updated_at        TEXT,
    FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE
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
    code TEXT,                  -- Код (давхцахгүй, гараас эсвэл seed-ээс)
    name TEXT NOT NULL          -- Албан тушаал
);

CREATE TABLE IF NOT EXISTS profession (
    id   INTEGER PRIMARY KEY,
    code TEXT,                  -- Код (давхцахгүй)
    name TEXT NOT NULL          -- Мэргэжил
);

-- Бүтцийн удирдлага (лавлах) — organization ба app_user хоёул эндээс сонгоно.
CREATE TABLE IF NOT EXISTS structure (
    id   INTEGER PRIMARY KEY,
    code TEXT,                  -- Код (давхцахгүй)
    name TEXT NOT NULL          -- Бүтцийн нэгжийн нэр
);

-- Шагнал, урамшууллын төрөл (лавлах) — member_reward эндээс сонгоно.
CREATE TABLE IF NOT EXISTS reward_type (
    id   INTEGER PRIMARY KEY,
    code TEXT,                  -- Код (давхцахгүй)
    name TEXT NOT NULL          -- Шагнал, урамшууллын нэр
);
"""

# ------------------------- Портал: динамик цэс ба контент (menu/content) -------------------------
# menu (Цэс) — порталын дээд цэс. type нь тухайн цэс дээр дарахад юу харагдахыг заана:
#   page     — динамик контент хуудас (админ бүрэн удирдана; page бичлэгтэй холбогдоно)
#   news/survey/poll/contact/home — кодод суусан функциональ хуудсууд (нэрлэх/нуух/эрэмбэлэх л боломжтой)
#   external — зөвхөн external_url руу үсэрнэ
# Гүн: цэс -> дэд цэс (2 түвшин). Дэд цэсний дэд цэс байхгүй (content.py-д шалгана).
SCHEMA_CONTENT = """
CREATE TABLE IF NOT EXISTS menu (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id    INTEGER,                     -- Дэд цэс бол эцэг цэсний id
    title        TEXT NOT NULL,               -- Цэсэнд харагдах нэр (ж: "Ковид")
    slug         TEXT NOT NULL UNIQUE,        -- URL хэсэг (ж: "covid")
    type         TEXT NOT NULL DEFAULT 'page',-- page / news / survey / poll / contact / home / external
    sort_order   INTEGER DEFAULT 0,           -- Эрэмбэ (нэг эцэг дотор)
    is_visible   INTEGER DEFAULT 1,           -- Порталд харагдах эсэх (0/1)
    external_url TEXT,                        -- type='external' үед заавал
    created_at   TEXT,
    updated_at   TEXT,
    FOREIGN KEY (parent_id) REFERENCES menu(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS page (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_id     INTEGER NOT NULL UNIQUE,      -- Аль цэсэнд харьяалагдах (нэг цэс = нэг хуудас)
    title       TEXT,                         -- Хуудасны том гарчиг
    body        TEXT,                         -- Rich text агуулга (HTML)
    cover_image TEXT,                         -- Дээд талын том зураг (URL)
    status      TEXT DEFAULT 'draft',         -- published / draft
    updated_at  TEXT,
    FOREIGN KEY (menu_id) REFERENCES menu(id) ON DELETE CASCADE
);

-- page_block — хуудасны агуулга нь ЭРЭМБЭТЭЙ БЛОКУУДААС бүрдэнэ (админ UI: "Блок нэмэх").
-- type: text (текст) / image (зураг) / video (видео) / file (файл) / link (холбоос).
-- Полиморф хүснэгт (contact-той ижил зарчим): төрлөөс хамаарч зөвхөн хэрэгтэй баганууд дүүрнэ.
--   text  -> text
--   image -> url, caption
--   video -> url (YouTube), title
--   file  -> url, name, mime_type, size
--   link  -> url, title
CREATE TABLE IF NOT EXISTS page_block (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id    INTEGER NOT NULL,
    type       TEXT NOT NULL,                 -- text / image / video / file / link
    sort_order INTEGER DEFAULT 0,             -- Блокийн эрэмбэ (↑↓)
    text       TEXT,                          -- type=text: rich text (HTML)
    url        TEXT,                          -- image/video/file/link: холбоос (/api/upload-аас)
    title      TEXT,                          -- video/link: гарчиг
    caption    TEXT,                          -- image: тайлбар
    name       TEXT,                          -- file: харагдах нэр
    mime_type  TEXT,                          -- file: ж: application/pdf
    size       INTEGER,                       -- file: байтаар
    FOREIGN KEY (page_id) REFERENCES page(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_menu_parent ON menu(parent_id);
CREATE INDEX IF NOT EXISTS idx_page_menu ON page(menu_id);
CREATE INDEX IF NOT EXISTS idx_page_block_page ON page_block(page_id);
"""

# ─── Судалгаа / Санал асуулга (survey & poll) ───────────────────────────────
# Нэг engine — form.type нь survey (судалгаа) эсвэл poll (санал асуулга).
# Бүтэц:  form -> form_question -> form_option
#         form -> form_document (poll-д хавсаргах PDF)
#         form -> form_submission -> form_answer -> form_answer_option
# Огноонууд "YYYY-MM-DD HH:MM:SS" (UTC) — SQLite-ийн DATE()-ээр өдрөөр бүлэглэнэ.
SCHEMA_FORM = """
CREATE TABLE IF NOT EXISTS form (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT NOT NULL DEFAULT 'survey',   -- survey / poll
    title        TEXT NOT NULL,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'draft',    -- draft / published / closed
    start_at     TEXT,                             -- эхлэх хугацаа (хоосон = хязгааргүй)
    end_at       TEXT,                             -- дуусах хугацаа
    show_results INTEGER NOT NULL DEFAULT 1,       -- порталд үр дүнг харуулах эсэх
    one_response INTEGER NOT NULL DEFAULT 1,       -- нэг хэрэглэгч нэг л удаа бөглөх
    created_by   INTEGER,                          -- app_user.id
    updated_by   INTEGER,
    created_at   TEXT,
    updated_at   TEXT,
    deleted_at   TEXT,                             -- зөөлөн устгал (хариулттай маягт)
    FOREIGN KEY (created_by) REFERENCES app_user(id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS form_question (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id       INTEGER NOT NULL,
    question_type TEXT NOT NULL,                   -- single_choice/multiple_choice/scale/open_text
    title         TEXT NOT NULL,                   -- асуултын текст
    description   TEXT,                            -- нэмэлт тайлбар
    is_required   INTEGER NOT NULL DEFAULT 0,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    settings      TEXT,                            -- JSON текст (scale: {"min":1,"max":5})
    created_at    TEXT,
    updated_at    TEXT,
    FOREIGN KEY (form_id) REFERENCES form(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS form_option (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    label       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT,
    updated_at  TEXT,
    FOREIGN KEY (question_id) REFERENCES form_question(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS form_document (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id    INTEGER NOT NULL,
    file_name  TEXT NOT NULL,                      -- анхны нэр (ж: labor-law-2026.pdf)
    file_path  TEXT NOT NULL,                      -- /uploads/form/<uuid>.pdf
    mime_type  TEXT,
    file_size  INTEGER,
    created_at TEXT,
    FOREIGN KEY (form_id) REFERENCES form(id) ON DELETE CASCADE
);

-- Нэг маягтад өгсөн нэг илгээмж.
-- UNIQUE индекс ТАВЬСАНГҮЙ — one_response=0 үед олон удаа бөглөх боломжтой байх ёстой
-- тул давхцлыг код дээр (client/forms.py) form.one_response-оос хамааруулж шалгана.
-- Портал НЭЭЛТТЭЙ (auth.py-ийн PUBLIC_PREFIXES) тул зочин ч бөглөж чадна —
-- тэр үед user_id нь NULL. Спекийн V1-д IP/төхөөрөмжөөр давхардал хязгаарлахгүй.
CREATE TABLE IF NOT EXISTS form_submission (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id      INTEGER NOT NULL,
    user_id      INTEGER,                          -- app_user.id; зочин бол NULL (FK тавиагүй)
    submitted_at TEXT,
    created_at   TEXT,
    FOREIGN KEY (form_id) REFERENCES form(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS form_answer (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    question_id   INTEGER NOT NULL,
    text_value    TEXT,                            -- open_text
    numeric_value REAL,                            -- scale
    created_at    TEXT,
    FOREIGN KEY (submission_id) REFERENCES form_submission(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES form_question(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS form_answer_option (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_id INTEGER NOT NULL,
    option_id INTEGER NOT NULL,
    FOREIGN KEY (answer_id) REFERENCES form_answer(id) ON DELETE CASCADE,
    FOREIGN KEY (option_id) REFERENCES form_option(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_form_question_form ON form_question(form_id);
CREATE INDEX IF NOT EXISTS idx_form_option_question ON form_option(question_id);
CREATE INDEX IF NOT EXISTS idx_form_document_form ON form_document(form_id);
CREATE INDEX IF NOT EXISTS idx_form_submission_form ON form_submission(form_id, user_id);
CREATE INDEX IF NOT EXISTS idx_form_answer_submission ON form_answer(submission_id);
CREATE INDEX IF NOT EXISTS idx_form_answer_question ON form_answer(question_id);
CREATE INDEX IF NOT EXISTS idx_form_answer_option_answer ON form_answer_option(answer_id);
CREATE INDEX IF NOT EXISTS idx_form_answer_option_option ON form_answer_option(option_id);
"""


# Сургуулийн ангиллын анхдагч өгөгдөл (Ангилал сургуулиуд.xlsx-аас).
# id нь бүртгэлийн кодны эхний 2 орон болдог тул 11-ээс эхэлнэ.
SCHOOL_CATEGORIES = [
    (11, "Сургуулийн өмнөх боловсрол", "СӨБ", "Early Childhood Education (Preschool)"),
    (12, "Ерөнхий боловсрол", "ЕБС", "General Education (Primary and Secondary Education)"),
    (13, "Мэргэжлийн боловсрол, сургалт", "МБС", "Technical and Vocational Education and Training (TVET)"),
    (14, "Их, дээд боловсрол", "ИДС", "Higher Education (Universities and Colleges)"),
    (15, "Шинжлэх ухаан", "ШУ", "Science / Research"),
    (16, "Боловсрол, шинжлэх ухааны туслах үйлчилгээ", "БШУТҮ", "Support Services in Education and Science"),
    (17, "Нэмэлт боловсрол", None, None),
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

# Бүтцийн удирдлагын лавлах (эх хүснэгтээс хэвээр).
# Эх нь I..V гэсэн салбар (Ром тоо) + доор нь дугаарласан нэгжүүдтэй боловч
# лавлах нь ХАВТГАЙ (id, code, name) тул код нь шатлалыг агуулна:
#   "II"   — салбарын гарчиг
#   "II.0" — тухайн салбарын "Хариуцсан мэргэжилтэн" (эхэд дугааргүй мөр)
#   "II.3" — тухайн салбарын 3 дугаартай нэгж
STRUCTURES = [
    (1,  "Сургуулийн өмнөх боловсролын ҮЭ-ийн хорооны дарга"),
    (2,  "Баянгол дүүрэг хариуцсан ҮЭ-ийн хорооны тэргүүлэгч"),
    (3,  "Баянзүрх дүүрэг хариуцсан ҮЭ-ийн хорооны тэргүүлэгч"),
    (4,  "Сүхбаатар дүүрэг хариуцсан ҮЭ-ийн хорооны тэргүүлэгч"),
    (5,  "Сонгинохайрхан дүүрэг хариуцсан ҮЭ-ийн хорооны тэргүүлэгч"),
    (6,  "Хан-Уул дүүрэг хариуцсан ҮЭ-ийн хорооны тэргүүлэгч"),
    (7,  "Чингэлтэй дүүрэг хариуцсан ҮЭ-ийн хорооны тэргүүлэгч"),
    (8,  "Ерөнхий Боловсролын Сургууль"),
    (9,  "Хариуцсан мэргэжилтэн"),
    (10, "Баянгол дүүргийн ЕБС-ийн ҮЭ-ийн хороодын зөвлөл"),
    (11, "Баянзүрх дүүргийн ЕБС-ийн ҮЭ-ийн хороодын зөвлөл"),
    (12, "Сүхбаатар дүүргийн ЕБС-ийн ҮЭ-ийн хороодын зөвлөл"),
    (13, "Сонгинохайрхан дүүргийн ЕБС-ийн ҮЭ-ийн хороодын зөвлөл"),
    (14, "Хан-Уул дүүргийн ЕБС-ийн ҮЭ-ийн хороодын зөвлөл"),
    (15, "Чингэлтэй дүүргийн ЕБС-ийн ҮЭ-ийн хороодын зөвлөл"),
    (16, "Их, дээд, мэргэжлийн сургууль"),
    (17, "Хариуцсан мэргэжилтэн"),
    (18, "Их, дээд, мэргэжлийн сургуулийн ҮЭ-ийн хороодын зөвлөл"),
    (19, "Шинжлэх ухааны байгууллагын ҮЭ-ийн нэгдсэн хороо"),
    (20, "Хариуцсан мэргэжилтэн"),
    (21, "Хөдөө, орон нутгийн ҮЭ-ийн хороодын зөвлөл"),
    (22, "Хариуцсан мэргэжилтэн"),
]

# structure.id -> эх хүснэгтийн № (шатлалыг агуулсан код)
STRUCTURE_CODES = {
    1: "I",    2: "I.1",  3: "I.2",  4: "I.3",  5: "I.4",  6: "I.5",  7: "I.6",
    8: "II",   9: "II.0", 10: "II.1", 11: "II.2", 12: "II.3", 13: "II.4",
    14: "II.5", 15: "II.6",
    16: "III", 17: "III.0", 18: "III.1",
    19: "IV",  20: "IV.0",
    21: "V",   22: "V.0",
}

# Шагнал, урамшууллын төрлийн лавлах (боловсролын салбарт нийтлэг тохиолддог)
REWARD_TYPES = [
    (1, "Хөдөлмөрийн баатар"),
    (2, "Алтан гадас одон"),
    (3, "Хөдөлмөрийн хүндэт медаль"),
    (4, "Боловсролын тэргүүний ажилтан"),
    (5, "Тэргүүний багш"),
    (6, "ҮЭ-ийн тэргүүний ажилтан"),
    (7, "Хүндэт жуух бичиг"),
    (8, "Баярын бичиг"),
    (9, "Өргөмжлөл"),
    (10, "Талархал"),
    (11, "Мөнгөн шагнал"),
    (12, "Үнэ бүхий зүйл"),
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
# Энд байгаа resource бүр нь API замтай тохирно (auth.py эндээс эрхийг гаргана).
PERMISSION_RESOURCES = [
    ("user", "Хэрэглэгч"),
    ("role", "Дүр"),
    ("permission", "Эрх"),
    ("admin_unit", "Засаг захиргааны нэгж"),
    ("school_category", "Сургуулийн ангилал"),
    ("holboo", "Холбоо"),
    ("horoo", "Хороо"),
    ("organization", "Байгууллага"),
    ("member", "Гишүүн"),
    ("member_education", "Гишүүний боловсрол"),
    ("member_file", "Гишүүний файл"),
    ("member_reward", "Гишүүний шагнал, урамшуулал"),
    ("contact", "Холбоо барих"),
    ("salary_request", "Цалингийн хүсэлт"),
    ("salary_scale", "Цалингийн шатлал"),
    ("education_degree", "Боловсролын зэрэг"),
    ("position", "Албан тушаал"),
    ("profession", "Мэргэжил"),
    ("reward_type", "Шагнал, урамшууллын төрөл"),
    ("structure", "Бүтцийн удирдлага"),
    # --- Портал: динамик цэс ба контент ---
    ("menu", "Цэс"),
    ("page", "Контент хуудас"),
    ("page_block", "Хуудасны блок"),
    ("page_image", "Хуудасны зураг"),
    ("page_file", "Хуудасны файл"),
    ("page_video", "Хуудасны видео"),
    ("upload", "Файл байршуулах"),
    # --- Судалгаа / Санал асуулга (survey & poll) ---
    ("form", "Судалгаа / Санал асуулга"),
    ("form_question", "Маягтын асуулт"),
    ("form_option", "Асуултын сонголт"),
    ("form_document", "Маягтын PDF"),
    ("form_submission", "Бөглөсөн хариулт"),
    ("form_result", "Судалгааны үр дүн"),
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
        ("union_card_code", "TEXT"),
        ("union_joined_date", "TEXT"),
        ("member_status", "TEXT"),
        ("status", "TEXT"),
        ("last_name", "TEXT"),
        ("position_id", "INTEGER"),
        ("profession_id", "INTEGER"),
        ("salary_scale_id", "INTEGER"),
        ("email", "TEXT"),
        ("au1_code", "TEXT"),
        ("au2_code", "TEXT"),
        ("au3_code", "TEXT"),
        ("signature", "INTEGER DEFAULT 0"),
        ("is_active", "INTEGER DEFAULT 1"),   # хуучин мөрүүд идэвхтэй гэж тооцогдоно
    ],
    "salary_request": [
        ("salary_scale_id", "INTEGER"),
    ],
    "organization": [
        ("phone1", "TEXT"),
        ("phone2", "TEXT"),
        ("email", "TEXT"),
        ("contact_name", "TEXT"),
        ("school_category_id", "INTEGER"),
        ("org_code", "TEXT"),
        ("state_reg_number", "TEXT"),
        ("postal_address", "TEXT"),
        ("structure_id", "INTEGER"),
        ("au1_code", "TEXT"),
        ("au2_code", "TEXT"),
        ("au3_code", "TEXT"),
    ],
    # Лавлахуудад код нэмэгдсэн (хуучин DB дээр NULL-ээр нэмэгдэж, seed нь дүүргэнэ)
    "position": [
        ("code", "TEXT"),
    ],
    "profession": [
        ("code", "TEXT"),
    ],
    "app_user": [
        ("last_name", "TEXT"),
        ("first_name", "TEXT"),
        ("structure_id", "INTEGER"),
    ],
    "horoo": [
        ("type", "TEXT"),
        ("registration_number", "TEXT"),
        ("founded_date", "TEXT"),
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
               ("ue_joined_date", "union_joined_date"),
               ("name", "first_name")],
    "member_education": [("surguuli", "school"), ("mergejil", "profession"),
                         ("tugssun_on", "graduation_year")],
    "education_degree": [("ner", "name")],
    "school_category": [("buten_ner", "full_name"), ("tovch_ner", "short_name"),
                        ("angli_ner", "english_name")],
}

# Устгах баганууд (хэрэв байгаа бол): хүснэгт -> [багана, ...]
# ЗӨВЛӨМЖ: утгыг нь шинэ бүтэц рүү зөөх бол _migrate_data()-д эхлээд бичих.
_DROP_COLUMNS = {
    "organization": ["org_type", "school_type"],
    "member": ["bolovsrol", "position", "profession", "phone_fax"],
    "app_user": ["full_name"],          # -> last_name + first_name (_migrate_data)
}

# Хуучин organization.school_type (чөлөөт текст) -> school_category.id
_SCHOOL_TYPE_MAP = {
    "СӨБ": 11,
    "ЕБС": 12,
    "МСҮТ": 13,
    "МБС": 13,
    "Их сургууль": 14,
    "ИДС": 14,
}

# Нэг удаа ажиллах өгөгдлийн шилжилтүүдийн хувилбар (PRAGMA user_version).
#   1 — school_category.id 1..7 -> 11..17 (код нь 2 орон тул тэглэх шаардлагагүй болно)
#   2 — position/profession.code-г 2 оронтой id-гаар нэг удаа дүүргэх
SCHEMA_VERSION = 2


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _lookup_id(conn, table, name):
    """Лавлах хүснэгтээс нэрээр id олно; байхгүй бол шинээр нэмж id-г нь буцаана."""
    row = conn.execute(f"SELECT id FROM {table} WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    return conn.execute(f"INSERT INTO {table}(name) VALUES (?)", (name,)).lastrowid


def _recompute_card_numbers(conn):
    """Гишүүдийн 9 оронтой батламжийн дугаарыг байгууллагын кодоос дахин бодно."""
    conn.execute(
        "UPDATE member SET union_card_number = ("
        "  SELECT printf('%02d', o.school_category_id) || o.org_code || member.union_card_code"
        "    FROM organization o WHERE o.id = member.organization_id) "
        "WHERE union_card_code IS NOT NULL")


def _shift_school_category_ids(conn):
    """school_category.id 1..7 -> 11..17 (нэг удаа; PRAGMA user_version-оор хамгаалагдана).

    id нь бүртгэлийн кодны эхний 2 орон учир 11-ээс эхэлбэл тэглэх (01) шаардлагагүй.
    FK зөрчихгүйн тулд: шинэ мөр нэмнэ -> байгууллагуудыг шинэ id рүү заана -> хуучныг устгана.
    """
    if conn.execute("PRAGMA user_version").fetchone()[0] >= 1:
        return
    for old in range(1, 8):
        new = old + 10
        row = conn.execute("SELECT * FROM school_category WHERE id=?", (old,)).fetchone()
        if not row or conn.execute(
                "SELECT 1 FROM school_category WHERE id=?", (new,)).fetchone():
            continue
        conn.execute(
            "INSERT INTO school_category(id, full_name, short_name, english_name) "
            "VALUES (?,?,?,?)",
            (new, row["full_name"], row["short_name"], row["english_name"]))
        conn.execute("UPDATE organization SET school_category_id=? WHERE school_category_id=?",
                     (new, old))
        conn.execute("DELETE FROM school_category WHERE id=?", (old,))
    _recompute_card_numbers(conn)          # ангилал өөрчлөгдсөн тул дугаарууд шинэчлэгдэнэ
    conn.execute("PRAGMA user_version = 1")


def _fill_ref_codes(conn):
    """Шинээр нэмэгдсэн position/profession.code-г 2 оронтой id-гаар дүүргэнэ (нэг удаа).

    Зөвхөн хоосон код бүхий мөрүүдэд хамаарна; дараа нь админ өөрөө засаж болно.
    """
    if conn.execute("PRAGMA user_version").fetchone()[0] >= 2:
        return
    for table in ("position", "profession"):
        conn.execute(
            f"UPDATE {table} SET code = printf('%02d', id) "
            "WHERE code IS NULL OR code = ''")
    conn.execute("PRAGMA user_version = 2")


def _migrate_data(conn):
    """Хуучин текст баганы утгыг шинэ бүтэц рүү зөөнө (баганыг устгахаас ӨМНӨ).

    - member.name ("Батын Болд") -> last_name + first_name
    - member.position / profession (текст) -> position_id / profession_id (лавлахын id)
    - member.phone_fax -> contact (owner_type='member', type='утас')
    - organization.school_type (текст) -> school_category_id
    - school_category.id 1..7 -> 11..17 (нэг удаа)
    - position/profession.code хоосон бол 2 оронтой id-гаар дүүргэх (нэг удаа)
    - app_user.full_name ("Батын Болд") -> last_name + first_name
    """
    _shift_school_category_ids(conn)   # ангиллын дугаарлалт эхэлж шинэчлэгдэнэ
    _fill_ref_codes(conn)              # position/profession.code (нэг удаа)
    member_cols = _cols(conn, "member")

    # 1) Овог+нэр салгах: зөвхөн хоосон last_name-тэй, зайтай нэрийг л хуваана
    if "last_name" in member_cols:
        for mid, full in conn.execute(
                "SELECT id, first_name FROM member "
                "WHERE last_name IS NULL AND first_name LIKE '% %'").fetchall():
            last, _, first = full.strip().partition(" ")
            conn.execute("UPDATE member SET last_name=?, first_name=? WHERE id=?",
                         (last, first.strip(), mid))

    # 1.1) app_user.full_name -> last_name + first_name (устгахаас ӨМНӨ)
    user_cols = _cols(conn, "app_user")
    if "full_name" in user_cols and "first_name" in user_cols:
        for uid, full in conn.execute(
                "SELECT id, full_name FROM app_user "
                "WHERE full_name IS NOT NULL AND full_name <> '' "
                "AND first_name IS NULL AND last_name IS NULL").fetchall():
            last, _, first = full.strip().partition(" ")
            # Зайгүй нэр (ж: "admin") бол бүхлээр нь нэр гэж үзнэ
            conn.execute("UPDATE app_user SET last_name=?, first_name=? WHERE id=?",
                         ((last if first else None), (first.strip() or last), uid))

    # 2) Албан тушаал / мэргэжлийн текстийг лавлахын id болгох (байхгүйг нь лавлахад нэмнэ)
    for col, table in (("position", "position"), ("profession", "profession")):
        if col not in member_cols or f"{col}_id" not in member_cols:
            continue
        for mid, val in conn.execute(
                f"SELECT id, {col} FROM member "
                f"WHERE {col} IS NOT NULL AND {col} <> '' AND {col}_id IS NULL").fetchall():
            conn.execute(f"UPDATE member SET {col}_id=? WHERE id=?",
                         (_lookup_id(conn, table, val), mid))

    # 3) Ганц phone_fax -> олон утас барих contact мөр
    if "phone_fax" in member_cols:
        for mid, phone in conn.execute(
                "SELECT id, phone_fax FROM member "
                "WHERE phone_fax IS NOT NULL AND phone_fax <> ''").fetchall():
            exists = conn.execute(
                "SELECT 1 FROM contact WHERE owner_type='member' AND owner_id=? AND value=?",
                (mid, phone)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO contact(owner_type, owner_id, type, value) "
                    "VALUES ('member', ?, 'утас', ?)", (mid, phone))

    # 4) school_type -> school_category_id (эхлээд тогтсон харгалзаа, дараа нь нэрээр)
    org_cols = _cols(conn, "organization")
    if "school_type" in org_cols and "school_category_id" in org_cols:
        for oid, st in conn.execute(
                "SELECT id, school_type FROM organization "
                "WHERE school_type IS NOT NULL AND school_type <> '' "
                "AND school_category_id IS NULL").fetchall():
            cid = _SCHOOL_TYPE_MAP.get(st)
            if cid is None:
                row = conn.execute(
                    "SELECT id FROM school_category WHERE short_name=? OR full_name=?",
                    (st, st)).fetchone()
                cid = row[0] if row else None
            if cid is not None:
                conn.execute("UPDATE organization SET school_category_id=? WHERE id=?",
                             (cid, oid))


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
        elif "address_detail" not in _cols(conn, table):
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
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
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


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.executescript(SCHEMA_UNION)
    conn.executescript(SCHEMA_REF)
    conn.executescript(SCHEMA_USER)
    conn.executescript(SCHEMA_CONTENT)
    conn.executescript(SCHEMA_FORM)
    _migrate(conn)
    _ensure_timestamps(conn)     # бүх хүснэгтэд created_at/updated_at + trigger
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


def _seed_coded_ref(table, data, label):
    """id+name лавлахыг ачаалж, code-г 2 оронтой id-гаар (01, 02 ...) дүүргэнэ.

    Хуучин DB дээр code багана саяхан нэмэгдсэн тул NULL үлдсэн мөрүүдийг ч дүүргэнэ.
    """
    init_db()
    conn = get_db()
    conn.executemany(
        f"INSERT OR IGNORE INTO {table}(id, code, name) VALUES (?, ?, ?)",
        [(i, f"{i:02d}", name) for i, name in data])
    conn.execute(
        f"UPDATE {table} SET code = printf('%02d', id) WHERE code IS NULL OR code = ''")
    conn.commit()
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    print(f"{label} ачаалагдлаа:", n)


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
    init_db()
    conn = get_db()
    conn.executemany(
        "INSERT OR IGNORE INTO structure(id, code, name) VALUES (?, ?, ?)",
        [(i, STRUCTURE_CODES.get(i, f"{i:02d}"), name) for i, name in STRUCTURES])
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM structure").fetchone()[0]
    conn.close()
    print("Бүтцийн удирдлага ачаалагдлаа:", n)


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


# Порталын анхдагч цэсний бүтэц: (slug, эцгийн slug | None, нэр, type, external_url)
# Дараалал нь sort_order болно. Гүн 2 түвшин (цэс -> дэд цэс).
DEFAULT_MENUS = [
    ("home",         None,    "Нүүр хуудас",     "home",     None),
    ("about",        None,    "Бидний тухай",    "page",     None),
    ("greeting",     "about", "Даргын мэндчилгээ", "page",   None),
    ("introduction", "about", "Танилцуулга",     "page",     None),
    ("vision",       "about", "Алсын хараа",     "page",     None),
    ("activity",     None,    "Үйл ажиллагаа",   "page",     None),
    ("news",         None,    "Мэдээ мэдээлэл",  "news",     None),
    ("survey",       None,    "Судалгаа",        "survey",   None),
    ("poll",         None,    "Санал асуулга",   "poll",     None),
    ("contact",      None,    "Холбоо барих",    "contact",  None),
]


def seed_menu():
    """Порталын анхдагч цэсний бүтцийг ачаална (menu хоосон үед л).

    type='page' цэс бүрд хоосон `page` бичлэг дагалдана — админ нь зөвхөн
    контентоо оруулахад л хангалттай болно.
    """
    init_db()
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM menu").fetchone()[0]:
        conn.close()
        print("Цэс аль хэдийн ачаалагдсан — алгаслаа.")
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids = {}            # slug -> id
    counters = {}       # эцгийн id (эсвэл None) -> sort_order тоолуур
    for slug, parent_slug, title, mtype, url in DEFAULT_MENUS:
        parent_id = ids.get(parent_slug) if parent_slug else None
        counters[parent_id] = counters.get(parent_id, 0) + 1
        cur = conn.execute(
            "INSERT INTO menu(parent_id, title, slug, type, sort_order, is_visible, "
            "external_url, created_at, updated_at) VALUES (?,?,?,?,?,1,?,?,?)",
            (parent_id, title, slug, mtype, counters[parent_id], url, now, now))
        ids[slug] = cur.lastrowid
        if mtype == "page":
            conn.execute(
                "INSERT INTO page(menu_id, title, status, updated_at) VALUES (?,?,?,?)",
                (cur.lastrowid, title, "draft", now))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM menu").fetchone()[0]
    conn.close()
    print("Порталын цэс ачаалагдлаа:", n)


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
            "INSERT INTO app_user(username, password_hash, last_name, first_name, "
            "role_id, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            ("admin", generate_password_hash("admin123", method="pbkdf2"),
             "Систем", "Администратор", role_id("admin")),
        )
        conn.commit()
        print("Анхны хэрэглэгч үүслээ: admin / admin123 (нэвтэрсний дараа нууц үгээ солино уу)")

    # 5) 'admin' хэрэглэгчийг ҮРГЭЛЖ 'admin' дүртэй холбоно. Дүр устгагдаад role_id
    #    NULL болсон байсан ч сэргээнэ — default admin үргэлж бүх эрхтэй байхыг баталгаажуулна.
    cur.execute("UPDATE app_user SET role_id=? WHERE username='admin'", (role_id("admin"),))
    conn.commit()

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

    cur.execute(
        "INSERT INTO horoo(holboo_id, name, type, registration_number, founded_date) "
        "VALUES (?,?,?,?,?)",
        (holboo_id, "Сүхбаатар дүүргийн хороо", "Дүүргийн хороо",
         "2811234", "2005-04-12"),
    )
    horoo_id = cur.lastrowid

    cur.execute(
        """INSERT INTO organization
           (name, school_category_id, org_code, registration_number,
            state_reg_number, founded_date, activity_code, activity_name, parent_org,
            au1_code, au2_code, address_detail, postal_address,
            phone1, phone2, email, contact_name)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("АШУҮИС-ийн харьяа сургууль", 14, "001",  # 14 + 001 -> 14001
         "9923659", "9019001234", "2023-01-31", "8530",
         "Дээд боловсрол олгох үйл ажиллагаа",
         "Анагаахын шинжлэх ухааны үндэсний их сургууль",
         "011", "01101", "Ард Аюушийн гудамж", "Улаанбаатар 14210, ШУТИС-14-р байр",
         "70112233", "99112233", "info@example.mn", "Б.Болд"),
    )
    org_id = cur.lastrowid

    # union_card_number = байгууллагын 5 оронтой код (14001) + гишүүний 4 оронтой код
    cur.executemany(
        "INSERT INTO member(organization_id, last_name, first_name, gender, birth_date, "
        "union_card_code, union_card_number) VALUES (?,?,?,?,?,?,?)",
        [
            (org_id, "Батын", "Болд", "эр", "1980-05-10", "0001", "140010001"),
            (org_id, "Доржийн", "Сараа", "эм", "1995-09-20", "0002", "140010002"),
            (org_id, "Цэрэнгийн", "Дулмаа", "эм", "2000-03-15", "0003", "140010003"),
            (org_id, "Наранбаатарын", "Ганбат", "эр", "1975-12-01", "0004", "140010004"),
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
    """Бүх домэйны seed-г дараалан ажиллуулна (`python db.py` үүнийг дуудна).

    Лавлахууд эхэлнэ — seed_union() тэдгээрийн id-г (ж: school_category_id) заана.
    """
    seed()
    seed_school_category()
    seed_salary_scale()
    seed_education_degree()
    seed_position()
    seed_profession()
    seed_reward_type()
    seed_structure()
    seed_union()
    seed_menu()
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
                or empty("salary_scale") or empty("position") or empty("profession")
                or empty("reward_type") or empty("structure"))
    need_menu = empty("menu")
    conn.close()

    # Лавлахууд эхэлнэ — seed_union() тэдгээрийн id-г заадаг (school_category_id).
    if need_ref:
        seed_school_category()
        seed_salary_scale()
        seed_education_degree()
        seed_position()
        seed_profession()
        seed_reward_type()
        seed_structure()
    if need_units:
        seed()
        seed_union()
    if need_menu:
        seed_menu()
    # Эрх/дүрийг ҮРГЭЛЖ синк хийнэ (idempotent): шинэ resource-ийн эрхүүд нэмэгдэж,
    # admin бүх эрхээ авна. Анхны admin хэрэглэгч зөвхөн app_user хоосон үед л үүснэ.
    seed_users()


if __name__ == "__main__":
    seed_all()
