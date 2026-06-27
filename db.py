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
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL,        -- Аль байгууллагад бүртгэлтэй
    name            TEXT NOT NULL,           -- Гишүүний нэр
    gender          TEXT,                    -- 'эр' / 'эм'
    birth_date      TEXT,                    -- Төрсөн огноо (YYYY-MM-DD)
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

CREATE TABLE IF NOT EXISTS salary_request (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id    INTEGER NOT NULL,            -- Аль гишүүний цалингийн хүсэлт
    salbar       TEXT,                        -- Салбар (СӨБ ба ЕБС / Мэргэжлийн боловсрол / Шинжлэх ухаан)
    kod          TEXT,                        -- Код (ТҮБД-5, ТҮМБ-3, ТҮШУУ-7 гэх мэт)
    albn_tushaal TEXT,                        -- Албан тушаал
    tsalin       INTEGER,                     -- Хүссэн цалингийн дүн (төгрөг)
    status       TEXT NOT NULL DEFAULT 'хүлээгдэж буй',  -- хүлээгдэж буй / зөвшөөрсөн / татгалзсан
    request_date TEXT,                        -- Хүсэлт гаргасан огноо (YYYY-MM-DD)
    note         TEXT,                        -- Тайлбар (сонголтоор)
    FOREIGN KEY (member_id) REFERENCES member(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_horoo_holboo ON horoo(holboo_id);
CREATE INDEX IF NOT EXISTS idx_org_horoo ON organization(horoo_id);
CREATE INDEX IF NOT EXISTS idx_member_org ON member(organization_id);
CREATE INDEX IF NOT EXISTS idx_contact_owner ON contact(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_salreq_member ON salary_request(member_id);
"""


def get_db():
    """Мөр бүрийг dict шиг хандах боломжтой холболт буцаана."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.executescript(SCHEMA_UNION)
    conn.commit()
    conn.close()


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
