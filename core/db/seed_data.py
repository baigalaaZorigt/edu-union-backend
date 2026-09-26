"""Засаг захиргааны нэгж (JSON) ба үйлдвэрчний эвлэлийн жишээ өгөгдлийн seed."""

import json
import os

from core.db import BASE_DIR, get_db
from core.db.schema import init_db


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
