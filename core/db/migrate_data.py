"""Хуучин SQLite DB-г шинэчлэх: нэмэх/нэрлэх/хасах багана ба өгөгдөл зөөх."""


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
        # Анхны нэвтрэлт / onboarding — анхдагч 0 тул БАЙГАА хэрэглэгчид
        # (админ ч гэсэн) нууц үг солихыг шаардахгүй; шинээр үүсгэсэн
        # хэрэглэгч POST /api/user дээр 1 болно.
        ("must_change_password", "INTEGER DEFAULT 0"),
        ("onboarding_completed_at", "TEXT"),
    ],
    "horoo": [
        ("type", "TEXT"),
        ("registration_number", "TEXT"),
        ("founded_date", "TEXT"),
    ],
    # Мэдээний цэс аль ангиллыг харуулахыг заана (NULL = бүх ангилал)
    "menu": [
        ("news_category", "TEXT"),
    ],
    # picked хаяглалтын хэрэглэгчид (JSON) — схемд хожим нэмэгдсэн тул хуучин
    # хүснэгт дээр `CREATE TABLE IF NOT EXISTS` нөхөж чадахгүй.
    "notifications": [
        ("audience_user_ids", "TEXT"),
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
