"""Үйлдвэрчний эвлэлийн бүтцийн CRUD (Blueprint).

Түвшин: holboo (Холбоо) -> horoo (Хороо) -> organization (Гишүүн байгууллага) -> member (Гишүүн)
Нэмэлт: contact (Холбоо барих) — хороо/байгууллагад полиморфоор харьяалагдана.
"""
from flask import Blueprint, jsonify, request, abort

from db import get_db
from helpers import rows, require, json_body

bp = Blueprint("union", __name__)

OWNER_TYPES = ("horoo", "organization")
CONTACT_TYPES = ("утас", "факс", "и-мэйл")
SCHOOL_TYPES = ("Их сургууль", "СӨБ", "ЕБС", "МСҮТ")

# Гишүүний бүртгэлийн талбарууд (organization_id-аас бусад, оруулж/засаж болох).
# Боловсрол (#10) нь member_education хүснэгтэд олноор бүртгэгдэнэ.
MEMBER_FIELDS = (
    "name", "birth_date", "gender", "register_number", "union_card_number",
    "union_joined_date", "member_status", "position", "profession",
    "phone_fax", "au1_code", "au2_code", "au3_code", "address_detail", "signature",
)

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

# Байгууллагын бүх талбар (зөвхөн эдгээрийг л оруулж/засна)
ORG_FIELDS = (
    "name", "school_type", "registration_number", "founded_date",
    "activity_code", "activity_name", "parent_org",
    "au1_code", "au2_code", "au3_code", "address_detail",
)


# ----------------------------- Туслахууд -----------------------------
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


@bp.route("/api/horoo", methods=["POST"])
def create_horoo():
    data = request.get_json(silent=True)
    require(data, ["holboo_id", "name"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM holboo WHERE id=?", (data["holboo_id"],)).fetchone():
        conn.close()
        abort(400, description="holboo_id (эцэг холбоо) олдсонгүй")
    cur = conn.execute("INSERT INTO horoo(holboo_id, name) VALUES (?, ?)",
                       (data["holboo_id"], data["name"]))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify(id=new_id, holboo_id=data["holboo_id"], name=data["name"]), 201


@bp.route("/api/horoo/<int:hid>", methods=["PUT"])
def update_horoo(hid):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    cur = conn.execute("UPDATE horoo SET name=? WHERE id=?", (data["name"], hid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Хороо олдсонгүй")
    return jsonify(id=hid, name=data["name"])


@bp.route("/api/horoo/<int:hid>", methods=["DELETE"])
def delete_horoo(hid):
    conn = get_db()
    cur = conn.execute("DELETE FROM horoo WHERE id=?", (hid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Хороо олдсонгүй")
    return jsonify(deleted=hid)


# =================== organization (Гишүүн байгууллага) ===================
@bp.route("/api/organization", methods=["GET"])
def list_org():
    horoo_id = request.args.get("horoo_id")
    conn = get_db()
    if horoo_id:
        data = rows(conn.execute(
            "SELECT * FROM organization WHERE horoo_id=? ORDER BY id", (horoo_id,)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM organization ORDER BY id").fetchall())
    for o in data:
        o.update(org_stats(conn, o["id"]))
    conn.close()
    return jsonify(data)


@bp.route("/api/organization/<int:oid>", methods=["GET"])
def get_org(oid):
    conn = get_db()
    row = conn.execute("SELECT * FROM organization WHERE id=?", (oid,)).fetchone()
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
    st = data.get("school_type")
    if st and st not in SCHOOL_TYPES:
        abort(400, description="school_type буруу. Сонголт: " + ", ".join(SCHOOL_TYPES))


@bp.route("/api/organization", methods=["POST"])
def create_org():
    data = request.get_json(silent=True)
    require(data, ["horoo_id", "name"])
    _validate_org(data)
    conn = get_db()
    if not conn.execute("SELECT 1 FROM horoo WHERE id=?", (data["horoo_id"],)).fetchone():
        conn.close()
        abort(400, description="horoo_id (эцэг хороо) олдсонгүй")
    _check_au(conn, data)
    cols = ["horoo_id"] + list(ORG_FIELDS)
    vals = [data["horoo_id"]] + [data.get(f) for f in ORG_FIELDS]
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO organization({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify(id=new_id, **{c: v for c, v in zip(cols, vals)}), 201


@bp.route("/api/organization/<int:oid>", methods=["PUT"])
def update_org(oid):
    data = json_body()
    _validate_org(data)
    fields = [f for f in ORG_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    _check_au(conn, data)
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [oid]
    cur = conn.execute(f"UPDATE organization SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Байгууллага олдсонгүй")
    return jsonify(updated=oid, fields=fields)


@bp.route("/api/organization/<int:oid>", methods=["DELETE"])
def delete_org(oid):
    conn = get_db()
    cur = conn.execute("DELETE FROM organization WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Байгууллага олдсонгүй")
    return jsonify(deleted=oid)


# ======================= member (Гишүүн) =======================
@bp.route("/api/member", methods=["GET"])
def list_member():
    org_id = request.args.get("organization_id")
    conn = get_db()
    if org_id:
        data = rows(conn.execute(
            "SELECT * FROM member WHERE organization_id=? ORDER BY id", (org_id,)).fetchall())
    else:
        data = rows(conn.execute("SELECT * FROM member ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/member/<int:mid>", methods=["GET"])
def get_member(mid):
    conn = get_db()
    row = conn.execute("SELECT * FROM member WHERE id=?", (mid,)).fetchone()
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
    conn.close()
    return jsonify(out)


@bp.route("/api/member", methods=["POST"])
def create_member():
    data = request.get_json(silent=True)
    require(data, ["organization_id", "name"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM organization WHERE id=?",
                        (data["organization_id"],)).fetchone():
        conn.close()
        abort(400, description="organization_id (эцэг байгууллага) олдсонгүй")
    _check_au(conn, data)
    cols, vals = ["organization_id"], [data["organization_id"]]
    for f in MEMBER_FIELDS:
        if data.get(f) is not None:
            cols.append(f)
            vals.append(data[f])
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO member({', '.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM member WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/member/<int:mid>", methods=["PUT"])
def update_member(mid):
    data = json_body()
    fields = [f for f in MEMBER_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    _check_au(conn, data)
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
        abort(400, description="owner_type нь 'horoo' эсвэл 'organization' байх ёстой")
    if data["type"] not in CONTACT_TYPES:
        abort(400, description="type нь: " + ", ".join(CONTACT_TYPES))
    conn = get_db()
    table = "horoo" if data["owner_type"] == "horoo" else "organization"
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


@bp.route("/api/contact/<int:cid>", methods=["PUT"])
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


@bp.route("/api/salary_request/<int:sid>", methods=["PUT"])
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


@bp.route("/api/salary_scale/<int:sid>", methods=["PUT"])
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


@bp.route("/api/education_degree/<int:eid>", methods=["PUT"])
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


# ==================== position (Албан тушаал, лавлах) ====================
@bp.route("/api/position", methods=["GET"])
def list_position():
    conn = get_db()
    data = rows(conn.execute("SELECT * FROM position ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/position/<int:pid>", methods=["GET"])
def get_position(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM position WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Албан тушаал олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/position", methods=["POST"])
def create_position():
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
            f"INSERT INTO position({', '.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ id аль хэдийн бүртгэгдсэн байна")
    new_id = data.get("id") or cur.lastrowid
    row = conn.execute("SELECT * FROM position WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/position/<int:pid>", methods=["PUT"])
def update_position(pid):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    cur = conn.execute("UPDATE position SET name=? WHERE id=?", (data["name"], pid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Албан тушаал олдсонгүй")
    return jsonify(id=pid, name=data["name"])


@bp.route("/api/position/<int:pid>", methods=["DELETE"])
def delete_position(pid):
    conn = get_db()
    cur = conn.execute("DELETE FROM position WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Албан тушаал олдсонгүй")
    return jsonify(deleted=pid)


# ==================== profession (Мэргэжил, лавлах) ====================
@bp.route("/api/profession", methods=["GET"])
def list_profession():
    conn = get_db()
    data = rows(conn.execute("SELECT * FROM profession ORDER BY id").fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/profession/<int:pid>", methods=["GET"])
def get_profession(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM profession WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Мэргэжил олдсонгүй")
    return jsonify(dict(row))


@bp.route("/api/profession", methods=["POST"])
def create_profession():
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
            f"INSERT INTO profession({', '.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ id аль хэдийн бүртгэгдсэн байна")
    new_id = data.get("id") or cur.lastrowid
    row = conn.execute("SELECT * FROM profession WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@bp.route("/api/profession/<int:pid>", methods=["PUT"])
def update_profession(pid):
    data = request.get_json(silent=True)
    require(data, ["name"])
    conn = get_db()
    cur = conn.execute("UPDATE profession SET name=? WHERE id=?", (data["name"], pid))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Мэргэжил олдсонгүй")
    return jsonify(id=pid, name=data["name"])


@bp.route("/api/profession/<int:pid>", methods=["DELETE"])
def delete_profession(pid):
    conn = get_db()
    cur = conn.execute("DELETE FROM profession WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Мэргэжил олдсонгүй")
    return jsonify(deleted=pid)


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


@bp.route("/api/member_education/<int:eid>", methods=["PUT"])
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
