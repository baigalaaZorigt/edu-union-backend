"""Үйлдвэрчний эвлэлийн бүтцийн CRUD (Blueprint).

Түвшин: holboo (Холбоо) -> horoo (Хороо) -> organization (Гишүүн байгууллага) -> member (Гишүүн)
Нэмэлт: contact (Холбоо барих) — хороо/байгууллага/гишүүнд полиморфоор харьяалагдана
(нэг эзэмшигч ОЛОН утас/факс/и-мэйлтэй байж болно).
"""
import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, abort, send_file

from db import get_db
from helpers import rows, require, json_body

bp = Blueprint("union", __name__)

# --- Гишүүний хавсралт файл (батламж г.м.) ---
# Зөвхөн PDF, файл тус бүр дээд тал нь 10 MB. Диск дээр uploads/member/ дотор хадгална
# (UPLOAD_DIR орчны хувьсагчаар өөрчилж болно — тогтвортой disk руу заахад хэрэгтэй).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "member"))
MAX_FILE_SIZE = 10 * 1024 * 1024          # 10 MB (файл тус бүрд)
PDF_MAGIC = b"%PDF-"                       # PDF файлын эхний байтууд

# contact эзэмшигчийн төрлүүд — утга нь хүснэгтийн нэртэй яг таарна.
OWNER_TYPES = ("horoo", "organization", "member")
CONTACT_TYPES = ("утас", "факс", "и-мэйл")

# Хорооны талбарууд (holboo_id-аас бусад)
HOROO_FIELDS = ("name", "type", "registration_number", "founded_date")

# Гишүүний бүртгэлийн талбарууд (organization_id-аас бусад, оруулж/засаж болох).
# Боловсрол (#10) нь member_education, утас/факс (#11) нь contact хүснэгтэд
# (owner_type='member') олноор бүртгэгдэнэ.
# union_card_number энд БАЙХГҮЙ — тэр нь union_card_code-оос автоматаар бүрдэнэ.
MEMBER_FIELDS = (
    "last_name", "first_name", "birth_date", "gender", "register_number",
    "union_card_code", "union_joined_date", "member_status",
    "position_id", "profession_id", "salary_scale_id", "email",
    "au1_code", "au2_code", "au3_code", "address_detail", "signature", "is_active",
)

# --- Бүртгэлийн кодын бүтэц ---
# Сургуулийн ангилал (2) + байгууллагын код (3)          = байгууллагын код (5)
# байгууллагын код (5)  + гишүүний код (4)               = union_card_number (9)
ORG_CODE_LEN = 3          # organization.org_code — гараас
CARD_CODE_LEN = 4         # member.union_card_code — гараас
# SQL хэсэг: байгууллагын 5 оронтой код (аль нэг хэсэг нь дутуу бол NULL)
# Ангилал эсвэл код нь дутуу бол NULL (printf нь NULL-ыг '00' болгочихдог тул CASE хэрэгтэй)
ORG_FULL_CODE_SQL = ("CASE WHEN {t}.school_category_id IS NULL THEN NULL "
                     "ELSE printf('%02d', {t}.school_category_id) || {t}.org_code END")

# Цалингийн хүсэлт
SALARY_STATUSES = ("хүлээгдэж буй", "зөвшөөрсөн", "татгалзсан")
SALARY_SECTORS = ("СӨБ ба ЕБС", "Мэргэжлийн боловсрол", "Шинжлэх ухаан")
# Цалингийн хүсэлтийн засаж/оруулж болох талбарууд (member_id-аас бусад).
# sector/code/position/salary нь salary_scale_id өгсөн үед шатлалаас автоматаар хуулагдана.
SALARY_FIELDS = (
    "salary_scale_id", "sector", "code", "position", "salary",
    "status", "request_date", "note",
)
# Цалингийн шатлалын талбарууд
SALARY_SCALE_FIELDS = ("sector", "code", "position", "salary")

# Гишүүний боловсролын мөрийн талбарууд (member_id-аас бусад)
MEMBER_EDUCATION_FIELDS = ("education_degree_id", "school", "profession", "graduation_year")

# Гишүүний шагнал, урамшууллын мөрийн талбарууд (member_id-аас бусад).
# Нэг гишүүн ОЛОН шагналтай байж болно; төрлийг reward_type лавлахаас сонгоно.
MEMBER_REWARD_FIELDS = ("reward_type_id", "description", "reward_date")

# Кодтой лавлах хүснэгтүүдийн талбарууд (id-аас бусад)
CODED_REF_FIELDS = ("code", "name")

# Гишүүний шагналыг төрлийнх нь нэр/кодтой хамт унших SELECT
MEMBER_REWARD_SELECT = """
SELECT mr.*,
       rt.name AS reward_type_name,
       rt.code AS reward_type_code
  FROM member_reward mr
  LEFT JOIN reward_type rt ON rt.id = mr.reward_type_id
"""

# Байгууллагын бүх талбар (зөвхөн эдгээрийг л оруулж/засна)
ORG_FIELDS = (
    "name", "school_category_id", "org_code",
    "registration_number", "state_reg_number", "founded_date",
    "activity_code", "activity_name", "parent_org",
    "au1_code", "au2_code", "au3_code", "address_detail", "postal_address",
    "phone1", "phone2", "email", "contact_name",
)

# Гишүүнийг лавлах + байгууллагын кодтой нь хамт унших SELECT
MEMBER_SELECT = f"""
SELECT m.*,
       p.name  AS position_name,
       pr.name AS profession_name,
       ss.code AS salary_scale_code,
       ss.salary AS salary_scale_salary,
       {ORG_FULL_CODE_SQL.format(t='o')} AS organization_code,
       sc.short_name AS school_category_short_name
  FROM member m
  LEFT JOIN position      p  ON p.id  = m.position_id
  LEFT JOIN profession    pr ON pr.id = m.profession_id
  LEFT JOIN salary_scale  ss ON ss.id = m.salary_scale_id
  LEFT JOIN organization  o  ON o.id  = m.organization_id
  LEFT JOIN school_category sc ON sc.id = o.school_category_id
"""

# Байгууллагыг сургуулийн ангилал + 5 оронтой кодтой нь хамт унших SELECT
ORG_SELECT = f"""
SELECT o.*,
       sc.short_name AS school_category_short_name,
       sc.full_name  AS school_category_name,
       CASE WHEN o.school_category_id IS NULL THEN NULL
            ELSE printf('%02d', o.school_category_id) END AS school_category_code,
       {ORG_FULL_CODE_SQL.format(t='o')} AS full_code
  FROM organization o
  LEFT JOIN school_category sc ON sc.id = o.school_category_id
"""


# ----------------------------- Туслахууд -----------------------------
def _check_ref(conn, data, field, table, label):
    """Лавлах руу заасан id (ж: position_id) байгаа эсэхийг шалгана (байхгүй бол 400)."""
    val = data.get(field)
    if val is None:
        return
    if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (val,)).fetchone():
        conn.close()
        abort(400, description=f"{label} ({field}) олдсонгүй")


def _digit_code(value, length, label):
    """Яг `length` оронтой цифрэн код эсэхийг шалгаад текстээр буцаана (эс бөгөөс 400)."""
    code = str(value).strip()
    if not code.isdigit() or len(code) != length:
        abort(400, description=(
            f"{label} яг {length} оронтой тоо байх ёстой "
            f"(ж: '{'1'.zfill(length)}')"))
    return code


def _org_full_code(conn, org_id):
    """Байгууллагын 5 оронтой код: ангиллын 2 орон + org_code 3 орон (дутуу бол None)."""
    row = conn.execute(
        "SELECT school_category_id, org_code FROM organization WHERE id=?", (org_id,)).fetchone()
    if not row or row["school_category_id"] is None or not row["org_code"]:
        return None
    return f"{row['school_category_id']:02d}{row['org_code']}"


def _card_number(conn, org_id, card_code):
    """Гишүүний 9 оронтой батламжийн дугаар = байгууллагын 5 орон + гишүүний 4 орон."""
    full = _org_full_code(conn, org_id)
    if not full:
        conn.close()
        abort(400, description=(
            "Байгууллагад сургуулийн ангилал ба 3 оронтой код (org_code) "
            "тохируулаагүй тул батламжийн дугаар үүсгэх боломжгүй"))
    return full + card_code


def _check_card_unique(conn, card_number, member_id=None):
    """Батламжийн 9 оронтой дугаар давхардаж байвал 409."""
    sql = "SELECT id FROM member WHERE union_card_number=?"
    params = [card_number]
    if member_id is not None:
        sql += " AND id<>?"
        params.append(member_id)
    if conn.execute(sql, params).fetchone():
        conn.close()
        abort(409, description=f"Батламжийн дугаар {card_number} аль хэдийн бүртгэгдсэн байна")


def _validate_member(data):
    """Гишүүний JSON-ы энгийн шалгалт (DB холболт нээхээс ӨМНӨ дуудна).

    - member_status: лавлахгүй, гараас бичих ЧӨЛӨӨТ ТЕКСТ
    - union_card_code: яг 4 оронтой тоо (энэ нь union_card_number-ийн сүүлийн 4 орон)
    - is_active / signature: зөвхөн 0 эсвэл 1 (true/false-ыг хөрвүүлнэ)
    """
    for flag in ("is_active", "signature"):
        if data.get(flag) is not None:
            val = data[flag]
            if isinstance(val, bool):
                data[flag] = int(val)
            elif val in (0, 1, "0", "1"):
                data[flag] = int(val)
            else:
                abort(400, description=f"{flag} нь 0 эсвэл 1 байна")
    st = data.get("member_status")
    if st is not None and (not isinstance(st, str) or not st.strip()):
        abort(400, description="member_status зөвхөн текст байна (ж: 'идэвхтэй')")
    # union_card_number гараар бичигдэхгүй — union_card_code(4)-оос автоматаар бүрдэнэ
    if "union_card_number" in data:
        abort(400, description=(
            "union_card_number-г шууд өгөхгүй — 4 оронтой union_card_code илгээнэ "
            "(байгууллагын 5 оронтой кодтой нийлж 9 орон болно)"))
    if data.get("union_card_code") is not None:
        data["union_card_code"] = _digit_code(
            data["union_card_code"], CARD_CODE_LEN, "union_card_code")


def _member_refs(conn, data):
    """Гишүүний лавлах холбоосуудыг (албан тушаал, мэргэжил, цалингийн шатлал) шалгана."""
    _check_ref(conn, data, "position_id", "position", "Албан тушаал")
    _check_ref(conn, data, "profession_id", "profession", "Мэргэжил")
    _check_ref(conn, data, "salary_scale_id", "salary_scale", "Цалингийн шатлал")


def _check_au(conn, data):
    """Хаягийн au1/au2/au3 код өгсөн бол засаг захиргааны нэгжид байгаа эсэхийг шалгана."""
    checks = (
        ("au1_code", "admin_unit1", "code", "Аймаг/нийслэл (au1_code)"),
        ("au2_code", "admin_unit2", "au2_code", "Сум/дүүрэг (au2_code)"),
        ("au3_code", "admin_unit3", "au3_code", "Баг/хороо (au3_code)"),
    )
    for field, table, col, label in checks:
        val = data.get(field)
        if val and not conn.execute(
                f"SELECT 1 FROM {table} WHERE {col}=?", (val,)).fetchone():
            conn.close()
            abort(400, description=f"{label} олдсонгүй")


def _purge_orphan_contacts(conn):
    """Эзэмшигчгүй үлдсэн contact мөрүүдийг цэвэрлэнэ.

    contact нь полиморф тул FK-гүй — хороо/байгууллага/гишүүн устахад (мөн хороо
    устахад доорх байгууллага, гишүүд нь каскадаар устахад) энд гараар цэвэрлэнэ.
    """
    conn.execute(
        "DELETE FROM contact WHERE "
        "(owner_type='horoo' AND owner_id NOT IN (SELECT id FROM horoo)) OR "
        "(owner_type='organization' AND owner_id NOT IN (SELECT id FROM organization)) OR "
        "(owner_type='member' AND owner_id NOT IN (SELECT id FROM member))"
    )


def _purge_orphan_files(conn):
    """Гишүүн (эсвэл каскадаар байгууллага/хороо) устахад үлдсэн файлыг дискнээс арилгана."""
    if not os.path.isdir(UPLOAD_DIR):
        return
    keep = {r[0] for r in conn.execute("SELECT stored_name FROM member_file")}
    for folder in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, folder)
        if not os.path.isdir(path):
            continue
        for fname in os.listdir(path):
            if os.path.join(folder, fname) not in keep:
                os.remove(os.path.join(path, fname))
        if not os.listdir(path):
            os.rmdir(path)


def org_stats(conn, org_id):
    """Гишүүдээс автоматаар: нийт / эмэгтэй / 35-аас доош тоо."""
    row = conn.execute(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN gender='эм' THEN 1 ELSE 0 END) AS female,
             SUM(CASE WHEN birth_date IS NOT NULL
                       AND (julianday('now') - julianday(birth_date))/365.25 < 35
                      THEN 1 ELSE 0 END) AS under35
           FROM member WHERE organization_id=?""",
        (org_id,),
    ).fetchone()
    return {
        "total_members": row["total"] or 0,
        "female_members": row["female"] or 0,
        "under35_members": row["under35"] or 0,
    }


# 400/404/409 алдааны JSON хариу нь run.py дотор app-түвшинд төвлөрсөн.


# ======================= horoo (Хороо) =======================
@bp.route("/api/horoo", methods=["GET"])
def list_horoo():
    holboo_id = request.args.get("holboo_id")
    conn = get_db()
    if holboo_id:
        data = rows(conn.execute(
            "SELECT * FROM horoo WHERE holboo_id=? ORDER BY id", (holboo_id,)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM horoo ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/horoo/<int:hid>", methods=["GET"])
def get_horoo(hid):
    conn = get_db()
    row = conn.execute("SELECT * FROM horoo WHERE id=?", (hid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Хороо олдсонгүй")
    out = dict(row)
    out["contacts"] = rows(conn.execute(
        "SELECT * FROM contact WHERE owner_type='horoo' AND owner_id=? ORDER BY id",
        (hid,)).fetchall())
    conn.close()
    return jsonify(out)


@bp.route("/api/horoo", methods=["POST"])
def create_horoo():
    data = request.get_json(silent=True)
    require(data, ["holboo_id", "name"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM holboo WHERE id=?", (data["holboo_id"],)).fetchone():
        conn.close()
        abort(400, description="holboo_id (эцэг холбоо) олдсонгүй")
    cols, vals = ["holboo_id"], [data["holboo_id"]]
    for f in HOROO_FIELDS:
        if data.get(f) is not None:
            cols.append(f)
            vals.append(data[f])
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(f"INSERT INTO horoo({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM horoo WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/horoo/<int:hid>", methods=["PUT", "PATCH"])
def update_horoo(hid):
    data = json_body()
    fields = [f for f in HOROO_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [hid]
    conn = get_db()
    cur = conn.execute(f"UPDATE horoo SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Хороо олдсонгүй")
    return jsonify(updated=hid, fields=fields)


@bp.route("/api/horoo/<int:hid>", methods=["DELETE"])
def delete_horoo(hid):
    conn = get_db()
    cur = conn.execute("DELETE FROM horoo WHERE id=?", (hid,))
    if cur.rowcount:
        _purge_orphan_contacts(conn)
        _purge_orphan_files(conn)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Хороо олдсонгүй")
    return jsonify(deleted=hid)


# =================== organization (Гишүүн байгууллага) ===================
@bp.route("/api/organization", methods=["GET"])
def list_org():
    # ?school_category_id= шүүлтүүр (байгууллага хороонд харьяалагдахаа больсон)
    cat = request.args.get("school_category_id")
    conn = get_db()
    if cat:
        data = rows(conn.execute(
            ORG_SELECT + " WHERE o.school_category_id=? ORDER BY o.id", (cat,)).fetchall())
    else:
        data = rows(conn.execute(ORG_SELECT + " ORDER BY o.id").fetchall())
    for o in data:
        o.update(org_stats(conn, o["id"]))
    conn.close()
    return jsonify(data)


@bp.route("/api/organization/<int:oid>", methods=["GET"])
def get_org(oid):
    conn = get_db()
    row = conn.execute(ORG_SELECT + " WHERE o.id=?", (oid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Байгууллага олдсонгүй")
    out = dict(row)
    out.update(org_stats(conn, oid))
    out["contacts"] = rows(conn.execute(
        "SELECT * FROM contact WHERE owner_type='organization' AND owner_id=?", (oid,)).fetchall())
    conn.close()
    return jsonify(out)


def _validate_org(data):
    """org_code (3 орон) ба school_category_id-г шалгаж, тоон утга болгоно — DB нээхээс өмнө.

    Маягтаас ангилал нь "12" гэсэн ТЕКСТ хэлбэрээр ирдэг тул int болгож хэвийтгэнэ
    (эс бөгөөс кодын харьцуулалт/форматлалт дээр л мэдэгддэг алдаа үүснэ).
    Хоосон мөр ("") нь "утга алга" гэсэн үг — NULL болгож хадгална.
    """
    if data.get("org_code") is not None:
        data["org_code"] = _digit_code(data["org_code"], ORG_CODE_LEN, "org_code")
    if "school_category_id" in data:
        cat = data["school_category_id"]
        if isinstance(cat, str):
            cat = cat.strip()
            data["school_category_id"] = None if cat == "" else cat
            cat = data["school_category_id"]
        if cat is not None:
            try:
                data["school_category_id"] = int(cat)
            except (TypeError, ValueError):
                abort(400, description="school_category_id нь бүхэл тоо байх ёстой")


def _check_org_code_unique(conn, data, oid=None):
    """Ангилал+код (5 орон) давхардвал 409 — гишүүдийн батламжийн дугаар давхцахаас сэргийлнэ.

    Засварлах үед зөвхөн нэг хэсгийг нь илгээж болох тул дутуу хэсгийг DB-ээс нөхнө.
    """
    cat, code = data.get("school_category_id"), data.get("org_code")
    if oid is not None and (cat is None or code is None):
        cur = conn.execute(
            "SELECT school_category_id, org_code FROM organization WHERE id=?", (oid,)).fetchone()
        if cur:
            cat = cur["school_category_id"] if cat is None else cat
            code = cur["org_code"] if code is None else code
    if cat is None or not code:
        return
    sql = "SELECT id FROM organization WHERE school_category_id=? AND org_code=?"
    params = [cat, code]
    if oid is not None:
        sql += " AND id<>?"
        params.append(oid)
    if conn.execute(sql, params).fetchone():
        conn.close()
        abort(409, description=f"{cat:02d}{code} код өөр байгууллагад бүртгэгдсэн байна")


def _recompute_cards(conn, oid):
    """Байгууллагын код өөрчлөгдөхөд гишүүдийн 9 оронтой дугаарыг дахин бодно."""
    full = _org_full_code(conn, oid)
    if full:
        conn.execute(
            "UPDATE member SET union_card_number = ? || union_card_code "
            "WHERE organization_id=? AND union_card_code IS NOT NULL", (full, oid))
    else:   # ангилал/код нь дутуу болсон бол дугаарыг цэвэрлэнэ
        conn.execute("UPDATE member SET union_card_number = NULL WHERE organization_id=?", (oid,))


@bp.route("/api/organization", methods=["POST"])
def create_org():
    data = request.get_json(silent=True)
    require(data, ["name"])
    _validate_org(data)
    conn = get_db()
    _check_ref(conn, data, "school_category_id", "school_category", "Сургуулийн ангилал")
    _check_org_code_unique(conn, data)
    _check_au(conn, data)
    cols = list(ORG_FIELDS)
    vals = [data.get(f) for f in ORG_FIELDS]
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO organization({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(ORG_SELECT + " WHERE o.id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/organization/<int:oid>", methods=["PUT", "PATCH"])
def update_org(oid):
    data = json_body()
    _validate_org(data)
    fields = [f for f in ORG_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    _check_ref(conn, data, "school_category_id", "school_category", "Сургуулийн ангилал")
    _check_org_code_unique(conn, data, oid)
    _check_au(conn, data)
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [oid]
    cur = conn.execute(f"UPDATE organization SET {sets} WHERE id=?", vals)
    # Кодын аль нэг хэсэг өөрчлөгдвөл гишүүдийн батламжийн дугаарыг дахин бодно
    if cur.rowcount and ("org_code" in fields or "school_category_id" in fields):
        _recompute_cards(conn, oid)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Байгууллага олдсонгүй")
    return jsonify(updated=oid, fields=fields)


@bp.route("/api/organization/<int:oid>", methods=["DELETE"])
def delete_org(oid):
    conn = get_db()
    cur = conn.execute("DELETE FROM organization WHERE id=?", (oid,))
    if cur.rowcount:
        _purge_orphan_contacts(conn)
        _purge_orphan_files(conn)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Байгууллага олдсонгүй")
    return jsonify(deleted=oid)


# ======================= member (Гишүүн) =======================
@bp.route("/api/member", methods=["GET"])
def list_member():
    # ?organization_id= ба ?is_active= (0/1) шүүлтүүд — хосолж болно
    cond, params = [], []
    if request.args.get("organization_id"):
        cond.append("m.organization_id=?")
        params.append(request.args["organization_id"])
    if request.args.get("is_active") is not None:
        cond.append("m.is_active=?")
        params.append(1 if request.args["is_active"] in ("1", "true", "True") else 0)
    sql = MEMBER_SELECT + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY m.id"
    conn = get_db()
    data = rows(conn.execute(sql, params).fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/member/<int:mid>", methods=["GET"])
def get_member(mid):
    conn = get_db()
    row = conn.execute(MEMBER_SELECT + " WHERE m.id=?", (mid,)).fetchone()
    if not row:
        conn.close()
        abort(404, description="Гишүүн олдсонгүй")
    out = dict(row)
    # Боловсролыг зэргийн нэртэй нь хамт буцаана
    out["educations"] = rows(conn.execute(
        "SELECT me.*, ed.name AS education_degree_name "
        "FROM member_education me "
        "LEFT JOIN education_degree ed ON ed.id = me.education_degree_id "
        "WHERE me.member_id=? ORDER BY me.id", (mid,)).fetchall())
    # Утас/факс/и-мэйл нь олон байж болно — contact-оос (owner_type='member')
    out["contacts"] = rows(conn.execute(
        "SELECT * FROM contact WHERE owner_type='member' AND owner_id=? ORDER BY id",
        (mid,)).fetchall())
    # Шагнал, урамшуулал (олон байж болно) — төрлийнх нь нэртэй хамт
    out["rewards"] = rows(conn.execute(
        MEMBER_REWARD_SELECT + " WHERE mr.member_id=? ORDER BY mr.id", (mid,)).fetchall())
    # Хавсаргасан PDF файлууд (батламж г.м.)
    out["files"] = rows(conn.execute(
        "SELECT * FROM member_file WHERE member_id=? ORDER BY id", (mid,)).fetchall())
    conn.close()
    return jsonify(out)


@bp.route("/api/member", methods=["POST"])
def create_member():
    data = request.get_json(silent=True)
    require(data, ["organization_id", "first_name"])
    _validate_member(data)
    conn = get_db()
    if not conn.execute("SELECT 1 FROM organization WHERE id=?",
                        (data["organization_id"],)).fetchone():
        conn.close()
        abort(400, description="organization_id (эцэг байгууллага) олдсонгүй")
    _member_refs(conn, data)
    _check_au(conn, data)
    cols, vals = ["organization_id"], [data["organization_id"]]
    for f in MEMBER_FIELDS:
        if data.get(f) is not None:
            cols.append(f)
            vals.append(data[f])
    # 4 оронтой код өгсөн бол 9 оронтой батламжийн дугаарыг үүсгэнэ
    if data.get("union_card_code") is not None:
        card = _card_number(conn, data["organization_id"], data["union_card_code"])
        _check_card_unique(conn, card)
        cols.append("union_card_number")
        vals.append(card)
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO member({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(MEMBER_SELECT + " WHERE m.id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/member/<int:mid>", methods=["PUT", "PATCH"])
def update_member(mid):
    data = json_body()
    _validate_member(data)
    fields = [f for f in MEMBER_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    _member_refs(conn, data)
    _check_au(conn, data)
    # 4 оронтой кодыг сольсон бол 9 оронтой дугаарыг дахин үүсгэнэ
    if data.get("union_card_code") is not None:
        row = conn.execute("SELECT organization_id FROM member WHERE id=?", (mid,)).fetchone()
        if not row:
            conn.close()
            abort(404, description="Гишүүн олдсонгүй")
        card = _card_number(conn, row["organization_id"], data["union_card_code"])
        _check_card_unique(conn, card, mid)
        fields.append("union_card_number")
        data["union_card_number"] = card
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [mid]
    cur = conn.execute(f"UPDATE member SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Гишүүн олдсонгүй")
    return jsonify(updated=mid, fields=fields)


@bp.route("/api/member/<int:mid>", methods=["DELETE"])
def delete_member(mid):
    conn = get_db()
    cur = conn.execute("DELETE FROM member WHERE id=?", (mid,))
    if cur.rowcount:
        _purge_orphan_contacts(conn)
        _purge_orphan_files(conn)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Гишүүн олдсонгүй")
    return jsonify(deleted=mid)


# ======================= contact (Холбоо барих) =======================
@bp.route("/api/contact", methods=["GET"])
def list_contact():
    owner_type = request.args.get("owner_type")
    owner_id = request.args.get("owner_id")
    conn = get_db()
    if owner_type and owner_id:
        data = rows(conn.execute(
            "SELECT * FROM contact WHERE owner_type=? AND owner_id=? ORDER BY id",
            (owner_type, owner_id)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM contact ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/contact", methods=["POST"])
def create_contact():
    data = request.get_json(silent=True)
    require(data, ["owner_type", "owner_id", "type", "value"])
    if data["owner_type"] not in OWNER_TYPES:
        abort(400, description="owner_type буруу. Сонголт: " + ", ".join(OWNER_TYPES))
    if data["type"] not in CONTACT_TYPES:
        abort(400, description="type нь: " + ", ".join(CONTACT_TYPES))
    conn = get_db()
    table = data["owner_type"]          # owner_type нь хүснэгтийн нэртэй ижил
    if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (data["owner_id"],)).fetchone():
        conn.close()
        abort(400, description="Эзэмшигч (owner_id) олдсонгүй")
    cur = conn.execute(
        "INSERT INTO contact(owner_type, owner_id, type, value, note) VALUES (?,?,?,?,?)",
        (data["owner_type"], data["owner_id"], data["type"], data["value"], data.get("note")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify(id=new_id, **data), 201


@bp.route("/api/contact/<int:cid>", methods=["PUT", "PATCH"])
def update_contact(cid):
    data = json_body()
    if data.get("type") and data["type"] not in CONTACT_TYPES:
        abort(400, description="type нь: " + ", ".join(CONTACT_TYPES))
    allowed = ["type", "value", "note"]
    fields = [f for f in allowed if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [cid]
    conn = get_db()
    cur = conn.execute(f"UPDATE contact SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Холбоо барих мэдээлэл олдсонгүй")
    return jsonify(updated=cid, fields=fields)


@bp.route("/api/contact/<int:cid>", methods=["DELETE"])
def delete_contact(cid):
    conn = get_db()
    cur = conn.execute("DELETE FROM contact WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Холбоо барих мэдээлэл олдсонгүй")
    return jsonify(deleted=cid)


# ==================== salary_request (Цалингийн хүсэлт) ====================
def _validate_salary(data):
    st = data.get("status")
    if st and st not in SALARY_STATUSES:
        abort(400, description="status буруу. Сонголт: " + ", ".join(SALARY_STATUSES))
    sb = data.get("sector")
    if sb and sb not in SALARY_SECTORS:
        abort(400, description="sector буруу. Сонголт: " + ", ".join(SALARY_SECTORS))


def _apply_scale(conn, data):
    """salary_scale_id өгсөн бол шатлалаас sector/code/position/salary-г хуулж буцаана."""
    scale_id = data.get("salary_scale_id")
    if scale_id is None:
        return data
    sc = conn.execute("SELECT * FROM salary_scale WHERE id=?", (scale_id,)).fetchone()
    if not sc:
        conn.close()
        abort(400, description="salary_scale_id (цалингийн шатлал) олдсонгүй")
    merged = dict(data)
    for f in ("sector", "code", "position", "salary"):
        merged[f] = sc[f]
    return merged


@bp.route("/api/salary_request", methods=["GET"])
def list_salary():
    member_id = request.args.get("member_id")
    status = request.args.get("status")
    conn = get_db()
    sql = "SELECT * FROM salary_request"
    cond, params = [], []
    if member_id:
        cond.append("member_id=?")
        params.append(member_id)
    if status:
        cond.append("status=?")
        params.append(status)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY id"
    data = rows(conn.execute(sql, params).fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/salary_request/<int:sid>", methods=["GET"])
def get_salary(sid):
    conn = get_db()
    row = conn.execute("SELECT * FROM salary_request WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Цалингийн хүсэлт олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/salary_request", methods=["POST"])
def create_salary():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    _validate_salary(data)
    conn = get_db()
    if not conn.execute("SELECT 1 FROM member WHERE id=?", (data["member_id"],)).fetchone():
        conn.close()
        abort(400, description="member_id (эцэг гишүүн) олдсонгүй")
    data = _apply_scale(conn, data)  # шатлал сонгосон бол утгыг хуулна
    # Зөвхөн дамжуулсан талбарыг оруулна — оруулаагүй бол status DB-ийн default-аар бөглөгдөнө
    cols, vals = ["member_id"], [data["member_id"]]
    for f in SALARY_FIELDS:
        if data.get(f) is not None:
            cols.append(f)
            vals.append(data[f])
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO salary_request({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    out = conn.execute("SELECT * FROM salary_request WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(out)), 201


@bp.route("/api/salary_request/<int:sid>", methods=["PUT", "PATCH"])
def update_salary(sid):
    data = json_body()
    _validate_salary(data)
    conn = get_db()
    data = _apply_scale(conn, data)  # шатлал сонгосон бол sector/code/.../salary-г хуулна
    fields = [f for f in SALARY_FIELDS if f in data]
    if not fields:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [sid]
    cur = conn.execute(f"UPDATE salary_request SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Цалингийн хүсэлт олдсонгүй")
    return jsonify(updated=sid, fields=fields)


@bp.route("/api/salary_request/<int:sid>", methods=["DELETE"])
def delete_salary(sid):
    conn = get_db()
    cur = conn.execute("DELETE FROM salary_request WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Цалингийн хүсэлт олдсонгүй")
    return jsonify(deleted=sid)


# ==================== salary_scale (Цалингийн шатлал, лавлах) ====================
@bp.route("/api/salary_scale", methods=["GET"])
def list_salary_scale():
    sector = request.args.get("sector")
    conn = get_db()
    if sector:
        data = rows(conn.execute(
            "SELECT * FROM salary_scale WHERE sector=? ORDER BY id", (sector,)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM salary_scale ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/salary_scale/<int:sid>", methods=["GET"])
def get_salary_scale(sid):
    conn = get_db()
    row = conn.execute("SELECT * FROM salary_scale WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Цалингийн шатлал олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/salary_scale", methods=["POST"])
def create_salary_scale():
    data = request.get_json(silent=True)
    require(data, ["sector", "code"])
    conn = get_db()
    cols = list(SALARY_SCALE_FIELDS)
    vals = [data.get(f) for f in cols]
    ph = ", ".join("?" * len(cols))
    try:
        cur = conn.execute(
            f"INSERT INTO salary_scale({', '.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ код (code) аль хэдийн бүртгэгдсэн байна")
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM salary_scale WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/salary_scale/<int:sid>", methods=["PUT", "PATCH"])
def update_salary_scale(sid):
    data = json_body()
    fields = [f for f in SALARY_SCALE_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [sid]
    conn = get_db()
    try:
        cur = conn.execute(f"UPDATE salary_scale SET {sets} WHERE id=?", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ код (code) аль хэдийн бүртгэгдсэн байна")
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Цалингийн шатлал олдсонгүй")
    return jsonify(updated=sid, fields=fields)


@bp.route("/api/salary_scale/<int:sid>", methods=["DELETE"])
def delete_salary_scale(sid):
    conn = get_db()
    cur = conn.execute("DELETE FROM salary_scale WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Цалингийн шатлал олдсонгүй")
    return jsonify(deleted=sid)


# ================ education_degree (Боловсролын зэрэг, лавлах) ================
@bp.route("/api/education_degree", methods=["GET"])
def list_education_degree():
    conn = get_db()
    data = rows(conn.execute("SELECT * FROM education_degree ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/education_degree/<int:eid>", methods=["GET"])
def get_education_degree(eid):
    conn = get_db()
    row = conn.execute("SELECT * FROM education_degree WHERE id=?", (eid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Боловсролын зэрэг олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/education_degree", methods=["POST"])
def create_education_degree():
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    cols, vals = ["name"], [data["name"]]
    if data.get("id") is not None:
        cols.append("id")
        vals.append(data["id"])
    ph = ", ".join("?" * len(cols))
    try:
        cur = conn.execute(
            f"INSERT INTO education_degree({', '.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ id аль хэдийн бүртгэгдсэн байна")
    new_id = data.get("id") or cur.lastrowid
    row = conn.execute("SELECT * FROM education_degree WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/education_degree/<int:eid>", methods=["PUT", "PATCH"])
def update_education_degree(eid):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    cur = conn.execute("UPDATE education_degree SET name=? WHERE id=?", (data["name"], eid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Боловсролын зэрэг олдсонгүй")
    return jsonify(id=eid, name=data["name"])


@bp.route("/api/education_degree/<int:eid>", methods=["DELETE"])
def delete_education_degree(eid):
    conn = get_db()
    cur = conn.execute("DELETE FROM education_degree WHERE id=?", (eid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Боловсролын зэрэг олдсонгүй")
    return jsonify(deleted=eid)


# ============ Кодтой лавлахууд (position / profession / reward_type) ============
# Гурвуулаа ижил бүтэцтэй (id + code + name) тул CRUD-ыг доорх туслахууд хуваалцана.
def _check_code_unique(conn, table, code, label, exclude_id=None):
    """Лавлахын код давхцсан эсэхийг шалгана (DB-д UNIQUE байхгүй тул гараар, 409)."""
    if code is None or code == "":
        return
    sql, params = f"SELECT 1 FROM {table} WHERE code=?", [code]
    if exclude_id is not None:
        sql += " AND id<>?"
        params.append(exclude_id)
    if conn.execute(sql, params).fetchone():
        conn.close()
        abort(409, description=f"{label}: '{code}' код аль хэдийн бүртгэгдсэн байна")


def _ref_list(table):
    conn = get_db()
    data = rows(conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


def _ref_get(table, rid, label):
    conn = get_db()
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description=f"{label} олдсонгүй")
    return jsonify(dict(row))


def _ref_create(table, label):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    _check_code_unique(conn, table, data.get("code"), label)
    cols = [f for f in CODED_REF_FIELDS if data.get(f) is not None]
    vals = [data[f] for f in cols]
    if data.get("id") is not None:
        cols.append("id")
        vals.append(data["id"])
    ph = ", ".join("?" * len(cols))
    try:
        cur = conn.execute(f"INSERT INTO {table}({', '.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ id аль хэдийн бүртгэгдсэн байна")
    new_id = data.get("id") or cur.lastrowid
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


def _ref_update(table, rid, label):
    """code/name-ийн аль нэг эсвэл хоёуланг нь засна (хэсэгчилсэн засвар)."""
    data = json_body()
    fields = [f for f in CODED_REF_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    if "name" in data and not (data["name"] or "").strip():
        abort(400, description="name хоосон байж болохгүй")
    conn = get_db()
    _check_code_unique(conn, table, data.get("code"), label, rid)
    sets = ", ".join(f"{f}=?" for f in fields)
    cur = conn.execute(f"UPDATE {table} SET {sets} WHERE id=?",
                       [data[f] for f in fields] + [rid])
    conn.commit()
    if cur.rowcount == 0:
        conn.close()
        abort(404, description=f"{label} олдсонгүй")
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
    conn.close()
    return jsonify(dict(row))


def _ref_delete(table, rid, label):
    conn = get_db()
    cur = conn.execute(f"DELETE FROM {table} WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description=f"{label} олдсонгүй")
    return jsonify(deleted=rid)


# ==================== position (Албан тушаал, лавлах) ====================
@bp.route("/api/position", methods=["GET"])
def list_position():
    return _ref_list("position")


@bp.route("/api/position/<int:pid>", methods=["GET"])
def get_position(pid):
    return _ref_get("position", pid, "Албан тушаал")


@bp.route("/api/position", methods=["POST"])
def create_position():
    return _ref_create("position", "Албан тушаал")


@bp.route("/api/position/<int:pid>", methods=["PUT", "PATCH"])
def update_position(pid):
    return _ref_update("position", pid, "Албан тушаал")


@bp.route("/api/position/<int:pid>", methods=["DELETE"])
def delete_position(pid):
    return _ref_delete("position", pid, "Албан тушаал")


# ==================== profession (Мэргэжил, лавлах) ====================
@bp.route("/api/profession", methods=["GET"])
def list_profession():
    return _ref_list("profession")


@bp.route("/api/profession/<int:pid>", methods=["GET"])
def get_profession(pid):
    return _ref_get("profession", pid, "Мэргэжил")


@bp.route("/api/profession", methods=["POST"])
def create_profession():
    return _ref_create("profession", "Мэргэжил")


@bp.route("/api/profession/<int:pid>", methods=["PUT", "PATCH"])
def update_profession(pid):
    return _ref_update("profession", pid, "Мэргэжил")


@bp.route("/api/profession/<int:pid>", methods=["DELETE"])
def delete_profession(pid):
    return _ref_delete("profession", pid, "Мэргэжил")


# ============ reward_type (Шагнал, урамшууллын төрөл, лавлах) ============
@bp.route("/api/reward_type", methods=["GET"])
def list_reward_type():
    return _ref_list("reward_type")


@bp.route("/api/reward_type/<int:rid>", methods=["GET"])
def get_reward_type(rid):
    return _ref_get("reward_type", rid, "Шагналын төрөл")


@bp.route("/api/reward_type", methods=["POST"])
def create_reward_type():
    return _ref_create("reward_type", "Шагналын төрөл")


@bp.route("/api/reward_type/<int:rid>", methods=["PUT", "PATCH"])
def update_reward_type(rid):
    return _ref_update("reward_type", rid, "Шагналын төрөл")


@bp.route("/api/reward_type/<int:rid>", methods=["DELETE"])
def delete_reward_type(rid):
    return _ref_delete("reward_type", rid, "Шагналын төрөл")


# ================ member_education (Гишүүний боловсрол) ================
def _check_degree(conn, data):
    """education_degree_id өгсөн бол лавлахад байгаа эсэхийг шалгана."""
    eid = data.get("education_degree_id")
    if eid is None:
        return
    if not conn.execute("SELECT 1 FROM education_degree WHERE id=?", (eid,)).fetchone():
        conn.close()
        abort(400, description="education_degree_id (боловсролын зэрэг) олдсонгүй")


@bp.route("/api/member_education", methods=["GET"])
def list_member_education():
    member_id = request.args.get("member_id")
    conn = get_db()
    sql = ("SELECT me.*, ed.name AS education_degree_name "
           "FROM member_education me "
           "LEFT JOIN education_degree ed ON ed.id = me.education_degree_id")
    params = []
    if member_id:
        sql += " WHERE me.member_id=?"
        params.append(member_id)
    sql += " ORDER BY me.id"
    data = rows(conn.execute(sql, params).fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/member_education/<int:eid>", methods=["GET"])
def get_member_education(eid):
    conn = get_db()
    row = conn.execute("SELECT * FROM member_education WHERE id=?", (eid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Боловсролын бүртгэл олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/member_education", methods=["POST"])
def create_member_education():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM member WHERE id=?", (data["member_id"],)).fetchone():
        conn.close()
        abort(400, description="member_id (эцэг гишүүн) олдсонгүй")
    _check_degree(conn, data)
    cols, vals = ["member_id"], [data["member_id"]]
    for f in MEMBER_EDUCATION_FIELDS:
        if data.get(f) is not None:
            cols.append(f)
            vals.append(data[f])
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO member_education({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM member_education WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/member_education/<int:eid>", methods=["PUT", "PATCH"])
def update_member_education(eid):
    data = json_body()
    conn = get_db()
    _check_degree(conn, data)
    fields = [f for f in MEMBER_EDUCATION_FIELDS if f in data]
    if not fields:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [eid]
    cur = conn.execute(f"UPDATE member_education SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Боловсролын бүртгэл олдсонгүй")
    return jsonify(updated=eid, fields=fields)


@bp.route("/api/member_education/<int:eid>", methods=["DELETE"])
def delete_member_education(eid):
    conn = get_db()
    cur = conn.execute("DELETE FROM member_education WHERE id=?", (eid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Боловсролын бүртгэл олдсонгүй")
    return jsonify(deleted=eid)


# ============ member_reward (Гишүүний шагнал, урамшуулал) ============
# Нэг гишүүн ОЛОН шагналтай байж болно (member_education-тэй ижил зарчим).
def _check_reward_type(conn, data):
    """reward_type_id өгсөн бол лавлахад байгаа эсэхийг шалгана."""
    rid = data.get("reward_type_id")
    if rid is None:
        return
    if not conn.execute("SELECT 1 FROM reward_type WHERE id=?", (rid,)).fetchone():
        conn.close()
        abort(400, description="reward_type_id (шагналын төрөл) олдсонгүй")


@bp.route("/api/member_reward", methods=["GET"])
def list_member_reward():
    # ?member_id= ба ?reward_type_id= шүүлтүүд — хосолж болно
    cond, params = [], []
    for f in ("member_id", "reward_type_id"):
        if request.args.get(f):
            cond.append(f"mr.{f}=?")
            params.append(request.args[f])
    sql = (MEMBER_REWARD_SELECT
           + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY mr.id")
    conn = get_db()
    data = rows(conn.execute(sql, params).fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/member_reward/<int:rid>", methods=["GET"])
def get_member_reward(rid):
    conn = get_db()
    row = conn.execute(MEMBER_REWARD_SELECT + " WHERE mr.id=?", (rid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Шагналын бүртгэл олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/member_reward", methods=["POST"])
def create_member_reward():
    data = request.get_json(silent=True)
    require(data, ["member_id"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM member WHERE id=?", (data["member_id"],)).fetchone():
        conn.close()
        abort(400, description="member_id (эцэг гишүүн) олдсонгүй")
    _check_reward_type(conn, data)
    cols, vals = ["member_id"], [data["member_id"]]
    for f in MEMBER_REWARD_FIELDS:
        if data.get(f) is not None:
            cols.append(f)
            vals.append(data[f])
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO member_reward({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(MEMBER_REWARD_SELECT + " WHERE mr.id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/member_reward/<int:rid>", methods=["PUT", "PATCH"])
def update_member_reward(rid):
    data = json_body()
    conn = get_db()
    _check_reward_type(conn, data)
    fields = [f for f in MEMBER_REWARD_FIELDS if f in data]
    if not fields:
        conn.close()
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [rid]
    cur = conn.execute(f"UPDATE member_reward SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Шагналын бүртгэл олдсонгүй")
    return jsonify(updated=rid, fields=fields)


@bp.route("/api/member_reward/<int:rid>", methods=["DELETE"])
def delete_member_reward(rid):
    conn = get_db()
    cur = conn.execute("DELETE FROM member_reward WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Шагналын бүртгэл олдсонгүй")
    return jsonify(deleted=rid)


# ============ member_file (Гишүүний хавсралт — батламж г.м., зөвхөн PDF) ============
def _validate_pdf(f):
    """Оруулсан нэг файлыг шалгана: .pdf нэр, PDF агуулга, ≤10 MB. Буруу бол 400.

    DB холболт нээхээс ӨМНӨ дуудна — бүх файлыг эхлээд шалгаж байж хадгална
    (нэг нь буруу бол юу ч хадгалагдахгүй).
    """
    name = (f.filename or "").strip()
    if not name:
        abort(400, description="Файлын нэр хоосон байна")
    if not name.lower().endswith(".pdf"):
        abort(400, description=f"'{name}': зөвхөн PDF файл оруулна")
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size == 0:
        abort(400, description=f"'{name}': файл хоосон байна")
    if size > MAX_FILE_SIZE:
        abort(400, description=(
            f"'{name}': файл 10 MB-аас хэтэрсэн байна "
            f"({size / 1024 / 1024:.1f} MB)"))
    if f.stream.read(len(PDF_MAGIC)) != PDF_MAGIC:
        f.stream.seek(0)
        abort(400, description=f"'{name}': PDF файл биш байна")
    f.stream.seek(0)
    return name, size


def _save_pdf(f, member_id):
    """Файлыг uploads/member/<member_id>/<uuid>.pdf болгож хадгаад stored_name-г буцаана."""
    folder = os.path.join(UPLOAD_DIR, str(member_id))
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.pdf"
    f.save(os.path.join(folder, stored))
    return os.path.join(str(member_id), stored)


@bp.route("/api/member_file", methods=["GET"])
def list_member_file():
    member_id = request.args.get("member_id")
    conn = get_db()
    if member_id:
        data = rows(conn.execute(
            "SELECT * FROM member_file WHERE member_id=? ORDER BY id",
            (member_id,)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM member_file ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/member_file/<int:fid>", methods=["GET"])
def get_member_file(fid):
    conn = get_db()
    row = conn.execute("SELECT * FROM member_file WHERE id=?", (fid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Файл олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/member_file/<int:fid>/download", methods=["GET"])
def download_member_file(fid):
    """Файлын агуулгыг PDF-ээр буцаана (анхны нэрээр нь татагдана)."""
    conn = get_db()
    row = conn.execute("SELECT * FROM member_file WHERE id=?", (fid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Файл олдсонгүй")
    path = os.path.join(UPLOAD_DIR, row["stored_name"])
    if not os.path.isfile(path):
        abort(404, description="Файлын агуулга дискнээс олдсонгүй")
    return send_file(path, mimetype="application/pdf",
                     as_attachment=True, download_name=row["file_name"])


@bp.route("/api/member_file", methods=["POST"])
def upload_member_file():
    """Гишүүнд PDF хавсралт(ууд) оруулна — multipart/form-data.

    Талбарууд: member_id (заавал), file (олон удаа давтаж болно), note (сонголтоор).
    """
    member_id = (request.form.get("member_id") or "").strip()
    if not member_id.isdigit():
        abort(400, description="member_id (тоо) шаардлагатай — multipart/form-data-аар илгээнэ")
    files = [f for f in request.files.getlist("file") + request.files.getlist("files") if f]
    if not files:
        abort(400, description="Файл алга — 'file' талбараар (олон байж болно) илгээнэ")

    checked = [_validate_pdf(f) for f in files]   # бүгд зөв эсэхийг эхлээд шалгана

    conn = get_db()
    if not conn.execute("SELECT 1 FROM member WHERE id=?", (member_id,)).fetchone():
        conn.close()
        abort(400, description="member_id (эцэг гишүүн) олдсонгүй")
    note = request.form.get("note")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_ids = []
    for f, (name, size) in zip(files, checked):
        stored = _save_pdf(f, member_id)
        cur = conn.execute(
            "INSERT INTO member_file(member_id, file_name, stored_name, size, note, uploaded_at) "
            "VALUES (?,?,?,?,?,?)", (member_id, name, stored, size, note, now))
        new_ids.append(cur.lastrowid)
    conn.commit()
    ph = ", ".join("?" * len(new_ids))
    data = rows(conn.execute(
        f"SELECT * FROM member_file WHERE id IN ({ph}) ORDER BY id", new_ids).fetchall())
    conn.close()
    return jsonify(data), 201


@bp.route("/api/member_file/<int:fid>", methods=["PUT", "PATCH"])
def update_member_file(fid):
    """Зөвхөн тайлбарыг (note) засна — файлын агуулгыг солихгүй (дахин оруулна)."""
    data = json_body()
    if "note" not in data:
        abort(400, description="Шинэчлэх талбар алга (note)")
    conn = get_db()
    cur = conn.execute("UPDATE member_file SET note=? WHERE id=?", (data["note"], fid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Файл олдсонгүй")
    return jsonify(updated=fid, fields=["note"])


@bp.route("/api/member_file/<int:fid>", methods=["DELETE"])
def delete_member_file(fid):
    conn = get_db()
    cur = conn.execute("DELETE FROM member_file WHERE id=?", (fid,))
    if cur.rowcount:
        _purge_orphan_files(conn)   # мөр устсаны дараа дискнээс нь ч арилгана
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Файл олдсонгүй")
    return jsonify(deleted=fid)
