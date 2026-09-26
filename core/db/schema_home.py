"""Схем: порталын нүүр хуудас — баннер (banner) ба хамтрагч байгууллага (partner)."""


# ─── Баннер / слайдер ───────────────────────────────────────────────────────
# Нүүр хуудсанд нэг (эсвэл хэд хэдэн бол слайдер) баннер. Зураг нь /api/upload-оор
# орсон URL. starts_at/ends_at нь UTC "YYYY-MM-DD HH:MM:SS" (NULL = хязгааргүй) —
# цонхны гадна баннер порталд харагдахгүй.
# ─── Хамтрагч байгууллага ───────────────────────────────────────────────────
# Нүүр хуудасны "Хамтрагч байгууллагууд" холбоосууд (нэр + URL + нэг emoji).
SCHEMA_HOME = """
CREATE TABLE IF NOT EXISTS banner (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,                          -- img alt + (заавал биш) тайлбар
    image_url   TEXT NOT NULL,                 -- /api/upload-оор орсон зураг
    link_url    TEXT,                          -- дарахад очих хаяг (http(s):// эсвэл харьцангуй)
    sort_order  INTEGER NOT NULL DEFAULT 0,    -- бага нь эхэнд
    is_visible  INTEGER NOT NULL DEFAULT 1,    -- 1 = харагдана
    starts_at   TEXT,                          -- UTC; NULL = хязгааргүй
    ends_at     TEXT,                          -- UTC; NULL = хязгааргүй
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS partner (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                 -- ж: "Боловсролын яам"
    url         TEXT NOT NULL,                 -- бүтэн холбоос (http(s)://)
    icon        TEXT,                          -- нэг emoji, ж: "🏛️"
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_visible  INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT,
    updated_at  TEXT
);
"""
