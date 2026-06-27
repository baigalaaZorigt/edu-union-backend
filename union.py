"""Үйлдвэрчний эвлэлийн бүтцийн CRUD (Blueprint).

Түвшин: holboo (Холбоо) -> horoo (Хороо) -> organization (Гишүүн байгууллага) -> member (Гишүүн)
Нэмэлт: contact (Холбоо барих) — хороо/байгууллагад полиморфоор харьяалагдана.
"""
from flask import Blueprint, jsonify, request, abort

from db import get_db

bp = Blueprint("union", __name__)

OWNER_TYPES = ("horoo", "organization")
CONTACT_TYPES = ("утас", "факс", "и-мэйл")
SCHOOL_TYPES = ("Их сургууль", "СӨБ", "ЕБС", "МСҮТ")

# Цалингийн хүсэлт
SALARY_STATUSES = ("хүлээгдэж буй", "зөвшөөрсөн", "татгалзсан")
SALARY_SECTORS = ("СӨБ ба ЕБС", "Мэргэжлийн боловсрол", "Шинжлэх ухаан")
# Цалингийн хүсэлтийн засаж/оруулж болох талбарууд (member_id-аас бусад)
SALARY_FIELDS = (
    "salbar", "kod", "albn_tushaal", "tsalin", "status", "request_date", "note",
)

# Байгууллагын бүх талбар (зөвхөн эдгээрийг л оруулж/засна)
ORG_FIELDS = (
    "name", "org_type", "school_type", "registration_number", "founded_date",
    "activity_code", "activity_name", "parent_org", "address",
)


# ----------------------------- Туслахууд -----------------------------
def rows(r):
    return [dict(x) for x in r]


def require(data, fields):
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    miss = [f for f in fields if not data.get(f)]
    if miss:
        abort(400, description="Дутуу талбар: " + ", ".join(miss))


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


@bp.errorhandler(400)
@bp.errorhandler(404)
@bp.errorhandler(409)
def err(e):
    return jsonify(error=e.description), e.code


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
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    _validate_org(data)
    fields = [f for f in ORG_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [oid]
    conn = get_db()
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


@bp.route("/api/member", methods=["POST"])
def create_member():
    data = request.get_json(silent=True)
    require(data, ["organization_id", "name"])
    conn = get_db()
    if not conn.execute("SELECT 1 FROM organization WHERE id=?",
                        (data["organization_id"],)).fetchone():
        conn.close()
        abort(400, description="organization_id (эцэг байгууллага) олдсонгүй")
    cur = conn.execute(
        "INSERT INTO member(organization_id, name, gender, birth_date) VALUES (?,?,?,?)",
        (data["organization_id"], data["name"], data.get("gender"), data.get("birth_date")))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify(id=new_id, **data), 201


@bp.route("/api/member/<int:mid>", methods=["PUT"])
def update_member(mid):
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    allowed = ["name", "gender", "birth_date"]
    fields = [f for f in allowed if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [mid]
    conn = get_db()
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
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
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
    sb = data.get("salbar")
    if sb and sb not in SALARY_SECTORS:
        abort(400, description="salbar буруу. Сонголт: " + ", ".join(SALARY_SECTORS))


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
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    _validate_salary(data)
    fields = [f for f in SALARY_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [sid]
    conn = get_db()
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
