"""Порталын анхдагч цэс, тохиргоо ба хэрэглэгчийн удирдлагын seed — ORM-оор."""

import json

from sqlalchemy import select, update

from core.db.reference_data import DEFAULT_ROLES, PERMISSION_ACTIONS, PERMISSION_RESOURCES
from core.db.seed_ref import _utc_now_iso, count, insert_missing


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
    from core.orm import new_session
    from core.orm.models import Menu, Page
    s = new_session(include_deleted=True)
    try:
        if count(s, "menu"):
            print("Цэс аль хэдийн ачаалагдсан — алгаслаа.")
            return
        now = _utc_now_iso()
        ids = {}            # slug -> id
        counters = {}       # эцгийн id (эсвэл None) -> sort_order тоолуур
        for slug, parent_slug, title, mtype, url in DEFAULT_MENUS:
            parent_id = ids.get(parent_slug) if parent_slug else None
            counters[parent_id] = counters.get(parent_id, 0) + 1
            menu = Menu(parent_id=parent_id, title=title, slug=slug, type=mtype,
                        sort_order=counters[parent_id], is_visible=1, external_url=url,
                        created_at=now, updated_at=now)
            s.add(menu)
            s.flush()
            ids[slug] = menu.id
            if mtype == "page":
                s.add(Page(menu_id=menu.id, title=title, status="draft", updated_at=now))
                s.flush()
        s.commit()
        n = count(s, "menu")
    finally:
        s.close()
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
    from core.orm import new_session
    from core.orm.models import PortalSettings
    s = new_session(include_deleted=True)
    try:
        if count(s, "portal_settings"):
            print("Порталын тохиргоо аль хэдийн бий — алгаслаа.")
            return
        now = _utc_now_iso()
        values = dict(DEFAULT_PORTAL_SETTINGS)
        values["phones"] = json.dumps(values["phones"], ensure_ascii=False)
        s.add(PortalSettings(id=1, created_at=now, updated_at=now, **values))
        s.commit()
    finally:
        s.close()
    print("Порталын тохиргоо ачаалагдлаа.")


def seed_users():
    """Хэрэглэгчийн удирдлагын seed: CRUD эрхүүд, анхдагч дүрүүд, admin хэрэглэгч.

    - permission: нөөц × үйлдэл бүрээр (INSERT OR IGNORE — давхардлыг алгасна)
    - role: admin / manager / viewer
    - role_permission: admin→бүх, viewer→бүх read, manager→үйл ажиллагааны CRUD
    - app_user: анхны 'admin' хэрэглэгч (app_user хоосон үед л)
    """
    from core.orm import new_session
    from core.orm.models import AppUser, Permission, Role, RolePermission
    s = new_session(include_deleted=True)
    try:
        # 1) Эрхүүд (нөөц × үйлдэл) ба 2) дүрүүд — давхардлыг алгасна
        insert_missing(s, "permission", [
            {"code": f"{res}.{act}", "name": f"{res_label} {act_label}",
             "resource": res, "action": act}
            for res, res_label in PERMISSION_RESOURCES
            for act, act_label in PERMISSION_ACTIONS])
        insert_missing(s, "role", [{"name": n, "description": d} for n, d in DEFAULT_ROLES])
        s.commit()

        def role_id(name):
            return s.scalar(select(Role.id).where(Role.name == name))

        def assign(role_name, *where):
            """Тухайн дүрд нөхцөлд тохирох бүх эрхийг оноож (давхардлыг алгасна)."""
            rid = role_id(role_name)
            insert_missing(s, "role_permission", [
                {"role_id": rid, "permission_id": pid}
                for pid in s.scalars(select(Permission.id).where(*where))])

        # 3) Эрх оноох. admin дүрийн нуугдсан (soft delete) холбоосыг эхлээд сэргээнэ —
        #    эс бөгөөс insert_missing түүнийг "байгаа" гэж алгасаад admin эрхгүй үлдэнэ.
        s.execute(update(RolePermission).where(RolePermission.role_id == role_id("admin"),
                                               RolePermission.deleted_at.is_not(None))
                  .values(deleted_at=None))
        assign("admin")                                           # бүх эрх
        assign("viewer", Permission.action == "read")             # зөвхөн харах
        assign("manager",                                         # менежер: үйл ажиллагааны CRUD
               Permission.action.in_(("create", "read", "update")),
               Permission.resource.in_(("holboo", "horoo", "organization", "member",
                                        "salary_request", "salary_scale")))
        s.commit()

        # 4) Анхны admin хэрэглэгч (зөвхөн хэрэглэгч огт байхгүй үед)
        if count(s, "app_user") == 0:
            from werkzeug.security import generate_password_hash
            s.add(AppUser(username="admin",
                          password_hash=generate_password_hash("admin123", method="pbkdf2"),
                          last_name="Систем", first_name="Администратор",
                          role_id=role_id("admin"), is_active=1))
            s.commit()
            print("Анхны хэрэглэгч үүслээ: admin / admin123 (нэвтэрсний дараа нууц үгээ солино уу)")

        # 5) 'admin' хэрэглэгчийг ҮРГЭЛЖ 'admin' дүртэй холбоно. Дүр устгагдаад role_id
        #    NULL болсон байсан ч сэргээнэ — default admin үргэлж бүх эрхтэй байхыг баталгаажуулна.
        s.execute(update(AppUser).where(AppUser.username == "admin")
                  .values(role_id=role_id("admin")))
        s.commit()

        n_perm, n_role = count(s, "permission"), count(s, "role")
    finally:
        s.close()
    print(f"User management seed дууслаа: {n_perm} эрх, {n_role} дүр.")
