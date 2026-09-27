"""Схем: хэрэглэгчийн удирдлага, лавлах хүснэгтүүд, порталын цэс/контент."""


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
    code        TEXT,                    -- Дүрийн код (заавал биш; давхцлыг кодоор шалгана)
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
    -- Анхны нэвтрэлт (specialist_onboarding_api_spec.md §2). Анхдагч нь 0 —
    -- POST /api/user нь шинэ хэрэглэгчид 1-ийг ТОДОРХОЙ бичнэ, ингэснээр хуучин
    -- (эсвэл seed-ийн) хэрэглэгчид нууц үг солихыг шаардахгүй.
    must_change_password    INTEGER DEFAULT 0,  -- Нууц үг солих шаардлагатай эсэх (0/1)
    onboarding_completed_at TEXT,               -- Зөвлөх мэргэжилтний onboarding дууссан огноо
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE SET NULL,
    FOREIGN KEY (structure_id) REFERENCES structure(id) ON DELETE SET NULL
);

-- Хэрэглэгчийн ХАМРАХ ХҮРЭЭ (user_scope) — user_scope_api_spec.md.
-- Дүр нь "юу хийж болох"-ыг заадаг бол энэ нь "АЛЬ өгөгдлийг харах"-ыг заана.
-- Нэг хэрэглэгчид НЭГ мөр (user_id нь PRIMARY KEY тул 1:1).
--   Зөвлөх/Мэргэжилтэн: school_type + (rural бол organization_ids, эс бөгөөс
--                       district_au2_code)
--   Сургуулийн менежер: organization_id (яг нэг сургууль)
-- login_attempt — БУРУУ нэвтрэх оролдлого, brute-force хязгаарт (admin/users/login_guard.py).
-- gunicorn-ийн ажилтнууд хуваалцаж, дахин асахад ч хадгалагдах тул санах ойд биш DB-д.
CREATE TABLE IF NOT EXISTS login_attempt (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,                -- оролдсон нэр (байхгүй хэрэглэгч ч байж болно)
    ip         TEXT NOT NULL,
    created_at TEXT NOT NULL                 -- UTC "YYYY-MM-DD HH:MM:SS"
);
CREATE INDEX IF NOT EXISTS idx_login_attempt_ip ON login_attempt(ip, created_at);
CREATE INDEX IF NOT EXISTS idx_login_attempt_time ON login_attempt(created_at);

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
    news_category TEXT,                       -- type='news' үед: Мэдээ / Сургалт / NULL (бүгд)
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

-- portal_settings — ПОРТАЛЫН ТОХИРГОО: бүхэл системд ГАНЦ мөр (singleton, id=1).
-- Толгой хэсэг, нүүрийн баннер, холбоо барих мэдээлэл, газрын зураг — өмнө нь
-- portal.html дотор хатуу бичигдсэн байсныг админаас удирдах боломжтой болгов.
-- Жагсаалт/CRUD хэрэггүй: зөвхөн GET (унших) ба PUT/PATCH (бүхэлд нь дарж хадгалах).
CREATE TABLE IF NOT EXISTS portal_settings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,   -- үргэлж 1
    logo_url        TEXT,                     -- /api/upload-аас ирсэн лого
    header_title    TEXT,                     -- лого хажуугийн гарчиг
    header_subtitle TEXT,                     -- лого хажуугийн дэд гарчиг
    hero_badge      TEXT,                     -- баннерын дээд тэмдэглэгээ
    hero_title      TEXT,                     -- баннерын гарчиг
    hero_text       TEXT,                     -- баннерын тайлбар (урт текст)
    phones          TEXT,                     -- JSON массив: ["323555", ...]
    website         TEXT,
    facebook_url    TEXT,
    youtube_url     TEXT,
    address         TEXT,                     -- хаягийн бүтэн текст
    map_embed_url   TEXT,                     -- Google Maps embed iframe-ийн src
    created_at      TEXT,
    updated_at      TEXT
);
"""
