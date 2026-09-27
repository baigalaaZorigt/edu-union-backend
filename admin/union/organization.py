"""organization (Гишүүн байгууллага) — CRUD, бүртгэлийн код, хамрах хүрээ."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import fail, json_body, pick, require, rows, update_row, fetch_page, list_json
from core.scope_core import org_condition, require_org_in_scope

from admin.union import bp
from admin.union.common import (ORG_FULL_CODE_SQL, _arg_filters, _check_au, _check_ref,
                                _create, _delete_by_id, _digit_code, _org_full_code,
                                _purge_orphan_contacts, _purge_orphan_files, _where)


# --- Бүртгэлийн кодын бүтэц ---
# Сургуулийн ангилал (2) + байгууллагын код (3)          = байгууллагын код (5)
# байгууллагын код (5)  + гишүүний код (4)               = union_card_number (9)
ORG_CODE_LEN = 3          # organization.org_code — гараас

# Байгууллагын бүх талбар (зөвхөн эдгээрийг л оруулж/засна)
ORG_FIELDS = (
    "name", "school_category_id", "org_code",
    "registration_number", "state_reg_number", "founded_date",
    "activity_code", "activity_name", "parent_org",
    "au1_code", "au2_code", "au3_code", "address_detail", "postal_address",
    "phone1", "phone2", "email", "contact_name", "structure_id",
)

# Байгууллагыг сургуулийн ангилал + 5 оронтой кодтой нь хамт унших SELECT
ORG_SELECT = f"""
SELECT o.*,
       st.name AS structure_name,
       st.code AS structure_code,
       sc.short_name AS school_category_short_name,
       sc.full_name  AS school_category_name,
       CASE WHEN o.school_category_id IS NULL THEN NULL
            ELSE printf('%02d', o.school_category_id) END AS school_category_code,
       {ORG_FULL_CODE_SQL.format(t='o')} AS full_code
  FROM organization o
  LEFT JOIN school_category sc ON sc.id = o.school_category_id
  LEFT JOIN structure       st ON st.id = o.structure_id
"""
NOT_FOUND = "Байгууллага олдсонгүй"


def org_stats_many(conn, org_ids):
    """Олон байгууллагын гишүүдийн нийт / эмэгтэй / 35-аас доош тоог НЭГ query-ээр.

    Өмнө нь байгууллага бүрд тусдаа query (N+1) — PG дээр бүр нь сүлжээгээр явдаг байв.
    Гишүүнгүй байгууллага 0-ээр гарна.
    """
    zero = {"total_members": 0, "female_members": 0, "under35_members": 0}
    if not org_ids:
        return {}
    out = {oid: dict(zero) for oid in org_ids}
    ph = ", ".join("?" * len(org_ids))
    for r in conn.execute(
        f"""SELECT organization_id,
             COUNT(*) AS total,
             SUM(CASE WHEN gender='эм' THEN 1 ELSE 0 END) AS female,
             SUM(CASE WHEN birth_date IS NOT NULL
                       AND (julianday('now') - julianday(birth_date))/365.25 < 35
                      THEN 1 ELSE 0 END) AS under35
           FROM member WHERE organization_id IN ({ph}) GROUP BY organization_id""",
        list(org_ids),
    ).fetchall():
        out[r["organization_id"]] = {"total_members": r["total"] or 0,
                                     "female_members": r["female"] or 0,
                                     "under35_members": r["under35"] or 0}
    return out


def org_stats(conn, org_id):
    """Нэг байгууллагын гишүүдийн тоо (org_stats_many-ийн нэг элементтэй хувилбар)."""
    return org_stats_many(conn, [org_id])[org_id]


# =================== organization (Гишүүн байгууллага) ===================
@bp.route("/api/organization", methods=["GET"])
def list_org():
    # ?school_category_id= ба ?structure_id= шүүлтүүр — хосолж болно
    # (байгууллага хороонд харьяалагдахаа больсон)
    cond, params = _arg_filters(("school_category_id", "structure_id"), prefix="o.")
    conn = get_db()
    # Хамрах хүрээ — серверийн талд НЭМЭГДЭХ нөхцөл (спек §5)
    scope_cond, scope_params = org_condition(conn, alias="o")
    if scope_cond:
        cond.append(scope_cond)
        params += scope_params
    page_rows, meta = fetch_page(conn, ORG_SELECT + _where(cond) + " ORDER BY o.id", params)
    data = rows(page_rows)
    stats = org_stats_many(conn, [o["id"] for o in data])   # хуудасны мөрүүдэд, нэг query
    for o in data:
        o.update(stats[o["id"]])
    conn.close()
    return list_json(data, meta)


@bp.route("/api/organization/<int:oid>", methods=["GET"])
def get_org(oid):
    conn = get_db()
    require_org_in_scope(conn, oid)
    row = conn.execute(ORG_SELECT + " WHERE o.id=?", (oid,)).fetchone()
    if not row:
        fail(conn, 404, NOT_FOUND)
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
            cat = cat.strip() or None
        if cat is not None:
            try:
                cat = int(cat)
            except (TypeError, ValueError):
                abort(400, description="school_category_id нь бүхэл тоо байх ёстой")
        data["school_category_id"] = cat


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
        fail(conn, 409, f"{cat:02d}{code} код өөр байгууллагад бүртгэгдсэн байна")


def _recompute_cards(conn, oid):
    """Байгууллагын код өөрчлөгдөхөд гишүүдийн 9 оронтой дугаарыг дахин бодно."""
    full = _org_full_code(conn, oid)
    if full:
        conn.execute(
            "UPDATE member SET union_card_number = ? || union_card_code "
            "WHERE organization_id=? AND union_card_code IS NOT NULL", (full, oid))
    else:   # ангилал/код нь дутуу болсон бол дугаарыг цэвэрлэнэ
        conn.execute("UPDATE member SET union_card_number = NULL WHERE organization_id=?", (oid,))


def _check_org_refs(conn, data, oid=None):
    """Байгууллагын лавлах холбоос, 5 оронтой кодын давхцал, хаягийг шалгана."""
    _check_ref(conn, data, "school_category_id", "school_category", "Сургуулийн ангилал")
    _check_ref(conn, data, "structure_id", "structure", "Бүтцийн удирдлага")
    _check_org_code_unique(conn, data, oid)
    _check_au(conn, data)


@bp.route("/api/organization", methods=["POST"])
def create_org():
    data = request.get_json(silent=True)
    require(data, ["name"])
    _validate_org(data)
    conn = get_db()
    _check_org_refs(conn, data)
    return _create(conn, "organization", {f: data.get(f) for f in ORG_FIELDS},
                   ORG_SELECT + " WHERE o.id=?")


@bp.route("/api/organization/<int:oid>", methods=["PUT", "PATCH"])
def update_org(oid):
    data = json_body()
    _validate_org(data)
    values = pick(data, ORG_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    require_org_in_scope(conn, oid)
    _check_org_refs(conn, data, oid)
    count = update_row(conn, "organization", oid, values)
    # Кодын аль нэг хэсэг өөрчлөгдвөл гишүүдийн батламжийн дугаарыг дахин бодно
    if count and ("org_code" in values or "school_category_id" in values):
        _recompute_cards(conn, oid)
    conn.commit()
    conn.close()
    if count == 0:
        abort(404, description=NOT_FOUND)
    return jsonify(updated=oid, fields=list(values))


@bp.route("/api/organization/<int:oid>", methods=["DELETE"])
def delete_org(oid):
    conn = get_db()
    require_org_in_scope(conn, oid)
    return _delete_by_id(conn, "organization", oid, NOT_FOUND,
                         _purge_orphan_contacts, _purge_orphan_files)
