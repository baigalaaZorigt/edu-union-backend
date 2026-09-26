"""Схем: мэдээ, санал хүсэлт, мэдэгдэл, судалгаа/санал асуулга."""


# ─── Мэдээ, зар (news) ──────────────────────────────────────────────────────
# Портал дээр КАРТЛАГ жагсаалтаар харагдаж, нээхэд эрэмбэтэй блокуудаас бүрдсэн
# контент гарч ирнэ. Блокийн бүтэц нь page_block-той ЯГ ИЖИЛ (text/image/video/
# file/link) — ялгаа нь зөвхөн эцэг нь `page` биш `news` байна. Ингэснээр
# frontend-ийн блок засварлагч дахин бичигдэлгүй хоёуланд нь ажиллана.
#   category — "Мэдээ" / "Сургалт" (menu.news_category-оор цэс тус бүрд шүүгдэнэ)
#   status   — draft / published; published болмогц published_at сервер талд тавигдана
SCHEMA_NEWS = """
CREATE TABLE IF NOT EXISTS news (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'Мэдээ',   -- Мэдээ / Сургалт
    author          TEXT,                            -- нийтлэсэн хүний нэр
    cover_image_url TEXT,                            -- картын зураг (/api/upload)
    summary         TEXT,                            -- картад харагдах товч танилцуулга
    status          TEXT NOT NULL DEFAULT 'draft',   -- draft / published
    published_at    TEXT,                            -- нийтэлсэн хугацаа
    created_by      INTEGER,                         -- app_user.id
    updated_by      INTEGER,
    created_at      TEXT,
    updated_at      TEXT,
    deleted_at      TEXT,
    FOREIGN KEY (created_by) REFERENCES app_user(id) ON DELETE SET NULL,
    FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL
);

-- news_block — page_block-той ижил полиморф блок (эцэг нь news).
--   text  -> text
--   image -> url, caption
--   video -> url (YouTube), title
--   file  -> url, name, mime_type, size
--   link  -> url, title
CREATE TABLE IF NOT EXISTS news_block (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id    INTEGER NOT NULL,
    type       TEXT NOT NULL,                 -- text / image / video / file / link
    sort_order INTEGER DEFAULT 0,             -- блокийн эрэмбэ (↑↓)
    text       TEXT,                          -- type=text: rich text (HTML)
    url        TEXT,                          -- image/video/file/link: холбоос
    title      TEXT,                          -- video/link: гарчиг
    caption    TEXT,                          -- image: тайлбар
    name       TEXT,                          -- file: харагдах нэр
    mime_type  TEXT,                          -- file: ж: application/pdf
    size       INTEGER,                       -- file: байтаар
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_news_list ON news(category, status);
CREATE INDEX IF NOT EXISTS idx_news_block_news ON news_block(news_id);
"""


# ─── Санал хүсэлт, Өргөдөл гомдол (feedback_api_spec.md) ────────────────────
# Хоёр бие даасан ЖИЖИГ маягт — survey/news шиг "engine" биш тул нэг дундын
# загвар руу оруулаагүй (спекийн 1-р хэсэг). Порталаас ТОКЕНГҮЙ ирж, админ
# зөвхөн жагсаалт харж, устгана.
SCHEMA_FEEDBACK = """
CREATE TABLE IF NOT EXISTS suggestions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,                 -- Нэр
    email      TEXT NOT NULL,                 -- И-мэйл
    phone      TEXT NOT NULL,                 -- Утас
    message    TEXT NOT NULL,                 -- Санал хүсэлт
    status     TEXT NOT NULL DEFAULT 'new',   -- new / reviewed (V1-д зөвхөн 'new')
    created_at TEXT,
    updated_at TEXT
);

-- Өргөдөл, гомдол — санал хүсэлттэй ижил, дээрээс нь ХАВСРАЛТ (заавал биш).
-- Файлыг одоо байгаа POST /api/upload-аар байршуулж, буцаж ирсэн url-ийг
-- file_url-д хадгална (Мэдээ/Цэсний блоктой ЯГ ижил урсгал) — шинэ upload
-- маршрут байхгүй.
CREATE TABLE IF NOT EXISTS complaints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT NOT NULL,
    description TEXT NOT NULL,                -- Тайлбар
    file_url    TEXT,                         -- /uploads/content/<uuid>.<ext>
    file_name   TEXT,                         -- хэрэглэгчид харагдах файлын нэр
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  TEXT,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_suggestions_created ON suggestions(created_at);
CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);
"""


# ─── Мэдэгдэл (notification_api_spec.md) ────────────────────────────────────
# Админ бичиж илгээнэ -> fan-out -> хэрэглэгч бүр өөрийн inbox-доо (🔔) хүлээж авна.
# Нэг мэдэгдэл (notifications) + хүлээн авагч бүрт нэг мөр (notification_recipients).
SCHEMA_NOTIFY = """
CREATE TABLE IF NOT EXISTS notifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,                 -- гарчиг (≤300)
    body          TEXT NOT NULL,                 -- үндсэн текст
    type          TEXT NOT NULL DEFAULT 'info',  -- info / reminder / urgent
    image_url     TEXT,                          -- POST /api/upload-ийн url
    audience_type TEXT NOT NULL,                 -- all / role / picked
    role_id       INTEGER,                       -- audience_type='role' үед
    -- audience_type='picked' үед сонгосон хэрэглэгчдийн id (JSON массив текстээр,
    -- user_scope.organization_ids-тэй ижил хэв маяг). Хуваарьт мэдэгдлийг
    -- ИЛГЭЭХ МӨЧИД fan-out хийх тул сонголтыг хадгалах шаардлагатай.
    audience_user_ids TEXT,
    status        TEXT NOT NULL DEFAULT 'draft', -- draft / scheduled / sent
    scheduled_at  TEXT,                          -- хуваарьт цаг (ирээдүйд илгээх)
    sent_at       TEXT,                          -- fan-out болсон цаг
    created_by    INTEGER,                       -- app_user.id (илгээсэн админ)
    created_at    TEXT,
    updated_at    TEXT,
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES app_user(id) ON DELETE SET NULL
);

-- Fan-out: илгээх мөчид хамрах хэрэглэгч бүрт НЭГ мөр. read_at нь уншсан эсэх.
-- UNIQUE(notification_id, user_id) нь дахин илгээхийг (давхар inbox мөр) хаана —
-- ингэснээр хуваарьт мэдэгдлийг хэд ч удаа "dispatch" хийхэд аюулгүй.
CREATE TABLE IF NOT EXISTS notification_recipients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    read_at         TEXT,                        -- NULL = уншаагүй
    created_at      TEXT,
    updated_at      TEXT,
    UNIQUE (notification_id, user_id),
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notify_status ON notifications(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_notify_rcpt_user ON notification_recipients(user_id, read_at);
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
