"""Засаг захиргааны нэгж (JSON) ба үйлдвэрчний эвлэлийн жишээ өгөгдлийн seed — ORM-оор."""

import json
import os

from core.db import BASE_DIR
from core.db.seed_ref import count, insert_missing


def _load_json(name):
    # Seed JSON файлууд data/seed/ дотор байрлана.
    with open(os.path.join(BASE_DIR, "data", "seed", name), encoding="utf-8") as f:
        return json.load(f)


def seed():
    """JSON файлуудаас өгөгдлийг хүснэгтэд ачаална (давхардлыг алгасна)."""
    from core.orm import new_session
    au1 = _load_json("admin_unit1.json")
    au2 = _load_json("admin_unit2.json")
    au3 = _load_json("admin_unit3.json")
    # Зарим au3 мөрийн au2_code эх хүснэгтэд байхгүй байж болзошгүй тул шүүнэ.
    valid_au2 = {r["au2_code"] for r in au2}
    rows3 = [{k: r[k] for k in ("au3_code", "au3_name", "au1_code", "au2_code")}
             for r in au3 if r["au2_code"] in valid_au2]
    skipped = len(au3) - len(rows3)

    s = new_session()
    try:
        insert_missing(s, "admin_unit1", [{"code": r["code"], "name": r["name"]} for r in au1])
        insert_missing(s, "admin_unit2", [{k: r[k] for k in ("au2_code", "au2_name", "au1_code")}
                                          for r in au2])
        insert_missing(s, "admin_unit3", rows3)
        s.commit()
        counts = {t: count(s, t) for t in ("admin_unit1", "admin_unit2", "admin_unit3")}
    finally:
        s.close()
    print("Ачаалал дууслаа:", counts, "| алгассан au3:", skipped)


def seed_union():
    """Үйлдвэрчний эвлэлийн бүтцэд жишээ өгөгдөл нэмнэ (хоосон үед л)."""
    from core.orm import new_session
    from core.orm.models import Contact, Holboo, Horoo, Member, Organization
    s = new_session()
    try:
        if count(s, "holboo") > 0:
            print("Union өгөгдөл аль хэдийн орсон байна — алгаслаа.")
            return

        holboo = Holboo(name="Боловсрол, шинжлэх ухааны үйлдвэрчний эвлэлийн холбоо")
        s.add(holboo)
        s.flush()
        horoo = Horoo(holboo_id=holboo.id, name="Сүхбаатар дүүргийн хороо", type="Дүүргийн хороо",
                      registration_number="2811234", founded_date="2005-04-12")
        org = Organization(
            name="АШУҮИС-ийн харьяа сургууль", school_category_id=14, org_code="001",  # -> 14001
            registration_number="9923659", state_reg_number="9019001234",
            founded_date="2023-01-31", activity_code="8530",
            activity_name="Дээд боловсрол олгох үйл ажиллагаа",
            parent_org="Анагаахын шинжлэх ухааны үндэсний их сургууль",
            au1_code="011", au2_code="01101", address_detail="Ард Аюушийн гудамж",
            postal_address="Улаанбаатар 14210, ШУТИС-14-р байр",
            phone1="70112233", phone2="99112233", email="info@example.mn", contact_name="Б.Болд")
        s.add_all([horoo, org])
        s.flush()

        # union_card_number = байгууллагын 5 оронтой код (14001) + гишүүний 4 оронтой код
        for last, first, gender, born, code in (
                ("Батын", "Болд", "эр", "1980-05-10", "0001"),
                ("Доржийн", "Сараа", "эм", "1995-09-20", "0002"),
                ("Цэрэнгийн", "Дулмаа", "эм", "2000-03-15", "0003"),
                ("Наранбаатарын", "Ганбат", "эр", "1975-12-01", "0004")):
            s.add(Member(organization_id=org.id, last_name=last, first_name=first, gender=gender,
                         birth_date=born, union_card_code=code, union_card_number="14001" + code))
            s.flush()                               # id-ийн дараалал хуучинтай ижил
        for owner_type, owner_id, ctype, value, note in (
                ("horoo", horoo.id, "утас", "99112233", "захиргаа"),
                ("horoo", horoo.id, "и-мэйл", "horoo@example.mn", None),
                ("organization", org.id, "утас", "70112233", "нягтлан"),
                ("organization", org.id, "факс", "70112234", None),
                ("organization", org.id, "и-мэйл", "info@example.mn", None)):
            s.add(Contact(owner_type=owner_type, owner_id=owner_id, type=ctype, value=value,
                          note=note))
            s.flush()
        s.commit()
    finally:
        s.close()
    print("Union жишээ өгөгдөл нэмэгдлээ.")
