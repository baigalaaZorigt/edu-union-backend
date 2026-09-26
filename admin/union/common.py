"""ҮЭ-ийн модулиудын хуваалцсан тогтмол, SELECT-үүд ба туслах функцууд.

Маршрутын модулиуд (horoo, organization, member, ...) бүгд ижил хэв маягтай CRUD
тул list/get/create/update/delete-ийн давтагддаг биеийг доорх `_list_rows`,
`_get_one`, `_create`, `_update_by_id`, `_delete_by_id` хуваалцана.
"""
import os

from flask import abort, jsonify, request

from core.db import get_db
from core.helpers import fail, insert_row, rows, update_row
from core.storage import Area


# --- Гишүүний хавсралт файл (батламж г.м.) ---
# Production-д S3-т (core/storage.py, S3_BUCKET), локал/тестэд UPLOAD_DIR хавтсанд
# `<member_id>/<uuid>.pdf` нэрээр хадгална. Хэмжээ/төрлийн шалгалт member_file.py-д.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads", "member"))
MEMBER_STORE = Area("member", UPLOAD_DIR)

# --- Бүртгэлийн кодын бүтэц ---
# Сургуулийн ангилал (2) + байгууллагын код (3)          = байгууллагын код (5)
# байгууллагын код (5)  + гишүүний код (4)               = union_card_number (9)
# (ORG_CODE_LEN нь organization.py-д)
CARD_CODE_LEN = 4         # member.union_card_code — гараас
# SQL хэсэг: байгууллагын 5 оронтой код (аль нэг хэсэг нь дутуу бол NULL)
# Ангилал эсвэл код нь дутуу бол NULL (printf нь NULL-ыг '00' болгочихдог тул CASE хэрэгтэй)
ORG_FULL_CODE_SQL = ("CASE WHEN {t}.school_category_id IS NULL THEN NULL "
                     "ELSE printf('%02d', {t}.school_category_id) || {t}.org_code END")

# Гишүүний шагналыг төрлийнх нь нэр/кодтой хамт унших SELECT
MEMBER_REWARD_SELECT = """
SELECT mr.*,
       rt.name AS reward_type_name,
       rt.code AS reward_type_code
  FROM member_reward mr
  LEFT JOIN reward_type rt ON rt.id = mr.reward_type_id
"""


# ------------------------- Ерөнхий CRUD туслахууд -------------------------
def _arg_filters(fields, prefix=""):
    """?field=утга шүүлтүүдээс (хоосон бол алгасна) WHERE-ийн нөхцөл + параметр бүтээнэ."""
    cond, params = [], []
    for f in fields:
        if request.args.get(f):
            cond.append(f"{prefix}{f}=?")
            params.append(request.args[f])
    return cond, params


def _where(cond):
    """Нөхцөлүүдийг " WHERE a AND b" болгоно (хоосон бол хоосон мөр)."""
    return " WHERE " + " AND ".join(cond) if cond else ""


def _list_rows(sql, params=()):
    """SELECT-ийн бүх мөрийг JSON жагсаалтаар буцаана."""
    conn = get_db()
    data = rows(conn.execute(sql, params).fetchall())
    conn.close()
    return jsonify(data)


def _get_one(sql, params, not_found):
    """Нэг мөрийг JSON-оор буцаана (байхгүй бол 404 `not_found`)."""
    conn = get_db()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    if not row:
        abort(404, description=not_found)
    return jsonify(dict(row))


def _create(conn, table, values, select_sql):
    """Мөр нэмээд `select_sql` (…WHERE id=?)-ээр буцааж уншина → 201."""
    new_id = insert_row(conn, table, values)
    conn.commit()
    row = conn.execute(select_sql, (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


def _update_by_id(conn, table, rid, values, not_found):
    """`values`-ээр нэг мөрийг шинэчилнэ → {updated, fields} (мөр байхгүй бол 404)."""
    count = update_row(conn, table, rid, values)
    conn.commit()
    conn.close()
    if count == 0:
        abort(404, description=not_found)
    return jsonify(updated=rid, fields=list(values))


def _delete_by_id(conn, table, rid, not_found, *cleanups):
    """Нэг мөрийг устгана → {deleted} (байхгүй бол 404).

    Устгасан бол `cleanups` (conn-оо авдаг функцууд — ж: өнчин contact/файл
    цэвэрлэх) commit-оос өмнө дараалан ажиллана.
    """
    cur = conn.execute(f"DELETE FROM {table} WHERE id=?", (rid,))
    if cur.rowcount:
        for cleanup in cleanups:
            cleanup(conn)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description=not_found)
    return jsonify(deleted=rid)


# ----------------------------- Шалгалтууд -----------------------------
def _require_row(conn, table, value, message, col="id"):
    """`table`-д `col=value` мөр байгаа эсэхийг шалгана (байхгүй бол 400 `message`)."""
    if not conn.execute(f"SELECT 1 FROM {table} WHERE {col}=?", (value,)).fetchone():
        fail(conn, 400, message)


def _check_ref(conn, data, field, table, label):
    """Лавлах руу заасан id (ж: position_id) байгаа эсэхийг шалгана (байхгүй бол 400)."""
    if data.get(field) is not None:
        _require_row(conn, table, data[field], f"{label} ({field}) олдсонгүй")


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


# Хаягийн талбар -> (хүснэгт, багана, шошго)
_AU_CHECKS = (
    ("au1_code", "admin_unit1", "code", "Аймаг/нийслэл (au1_code)"),
    ("au2_code", "admin_unit2", "au2_code", "Сум/дүүрэг (au2_code)"),
    ("au3_code", "admin_unit3", "au3_code", "Баг/хороо (au3_code)"),
)


def _check_au(conn, data):
    """Хаягийн au1/au2/au3 код өгсөн бол засаг захиргааны нэгжид байгаа эсэхийг шалгана."""
    for field, table, col, label in _AU_CHECKS:
        if data.get(field):
            _require_row(conn, table, data[field], f"{label} олдсонгүй", col)


# ----------------------------- Цэвэрлэгээ -----------------------------
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
    """Гишүүн (эсвэл каскадаар байгууллага/хороо) устахад үлдсэн файлыг сангаас арилгана."""
    keep = {r[0].replace(os.sep, "/") for r in conn.execute("SELECT stored_name FROM member_file")}
    for name in MEMBER_STORE.names():
        if name.replace(os.sep, "/") not in keep:
            MEMBER_STORE.delete(name)

