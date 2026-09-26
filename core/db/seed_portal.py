"""Порталын анхдагч цэс, тохиргоо ба хэрэглэгчийн удирдлагын seed."""

import json

from core.db import get_db
from core.db.reference_data import DEFAULT_ROLES, PERMISSION_ACTIONS, PERMISSION_RESOURCES
from core.db.schema import init_db
from core.db.seed_ref import _utc_now_iso


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
    now = _utc_now_iso()
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


# Порталын тохиргооны АНХДАГЧ утгууд — portal.html дотор хатуу бичигдсэн байсан
# текстүүд. Хүснэгт хоосон үед л (эхний деплой) энэ мөр үүсэх тул админ засчихаад
# дахин seed ажиллуулахад утга нь буцаж дарагдахгүй.
DEFAULT_PORTAL_SETTINGS = {
    "logo_url": None,
    "header_title": "МБШУ-ны ҮЭ-ийн Холбоо",
    "header_subtitle": "Хөдөлмөрийн хүний төлөө",
    "hero_badge": "1924 оноос эхлэлтэй салбарын үйлдвэрчний эвлэлийн холбоо",
    "hero_title": "Боловсрол, шинжлэх ухааны салбарын ажилтнуудын эрх ашгийн төлөө",
    "hero_text": "Монголын Боловсрол, Шинжлэх Ухааны Үйлдвэрчний Эвлэлийн Холбоо нь "
                 "салбарын ажилтнуудын хөдөлмөрлөх эрх, хууль ёсны ашиг сонирхлыг "
                 "хамгаалах, нийгмийн баталгааг сайжруулах зорилготой нэгдэл юм.",
    "phones": ["323555", "313609", "326328", "70126927"],
    "website": "fmesu.mn",
    "facebook_url": "https://www.facebook.com/groups/1629671727055980/",
    "youtube_url": None,
    "address": "210646 Улаанбаатар хот, Чингэлтэй дүүрэг, 1-р хороо, Бага тойруу "
               "/15160/, Сүхбаатарын талбай, МҮЭ-ийн ордон 221, 315, 316, 317 тоот",
    "map_embed_url": None,
}


def seed_portal_settings():
    """Порталын тохиргооны ганц мөрийг анхдагч утгуудаар үүсгэнэ (хоосон үед л)."""
    init_db()
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM portal_settings").fetchone()[0]:
        conn.close()
        print("Порталын тохиргоо аль хэдийн бий — алгаслаа.")
        return
    now = _utc_now_iso()
    d = DEFAULT_PORTAL_SETTINGS
    conn.execute(
        "INSERT INTO portal_settings(id, logo_url, header_title, header_subtitle, "
        "hero_badge, hero_title, hero_text, phones, website, facebook_url, "
        "youtube_url, address, map_embed_url, created_at, updated_at) "
        "VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (d["logo_url"], d["header_title"], d["header_subtitle"], d["hero_badge"],
         d["hero_title"], d["hero_text"], json.dumps(d["phones"], ensure_ascii=False),
         d["website"], d["facebook_url"], d["youtube_url"], d["address"],
         d["map_embed_url"], now, now))
    conn.commit()
    conn.close()
    print("Порталын тохиргоо ачаалагдлаа.")


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
