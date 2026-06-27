"""Монголын засаг захиргааны нэгжийн CRUD — Flask + SQLite.

Гурван түвшин:
  admin_unit1 (аймаг/нийслэл)  -> code, name
  admin_unit2 (сум/дүүрэг)     -> au2_code, au2_name, au1_code
  admin_unit3 (баг/хороо)      -> au3_code, au3_name, au1_code, au2_code
"""
from flask import Flask, jsonify, request, abort

from db import get_db, init_db
from union import bp as union_bp

app = Flask(__name__)
app.json.ensure_ascii = False  # Кирилл үсгийг escape хийлгүй буцаах
app.register_blueprint(union_bp)  # Үйлдвэрчний эвлэлийн CRUD (/union, /api/holboo ...)


# ----------------------------- Туслах функцууд -----------------------------
def rows_to_list(rows):
    return [dict(r) for r in rows]


def require_fields(data, fields):
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    missing = [f for f in fields if not data.get(f)]
    if missing:
        abort(400, description=f"Дутуу талбар: {', '.join(missing)}")


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(409)
def handle_error(err):
    return jsonify(error=err.description), err.code


# ===================== admin_unit1 (Аймаг / Нийслэл) =====================
@app.route("/api/au1", methods=["GET"])
def list_au1():
    conn = get_db()
    rows = conn.execute("SELECT * FROM admin_unit1 ORDER BY code").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/au1/<code>", methods=["GET"])
def get_au1(code):
    conn = get_db()
    row = conn.execute("SELECT * FROM admin_unit1 WHERE code=?", (code,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Аймаг олдсонгүй")
    return jsonify(dict(row))


@app.route("/api/au1", methods=["POST"])
def create_au1():
    data = request.get_json(silent=True)
    require_fields(data, ["code", "name"])
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO admin_unit1(code, name) VALUES (?, ?)",
            (data["code"], data["name"]),
        )
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ код аль хэдийн бүртгэгдсэн байна")
    conn.close()
    return jsonify(data), 201


@app.route("/api/au1/<code>", methods=["PUT"])
def update_au1(code):
    data = request.get_json(silent=True)
    require_fields(data, ["name"])
    conn = get_db()
    cur = conn.execute(
        "UPDATE admin_unit1 SET name=? WHERE code=?", (data["name"], code)
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Аймаг олдсонгүй")
    return jsonify(code=code, name=data["name"])


@app.route("/api/au1/<code>", methods=["DELETE"])
def delete_au1(code):
    conn = get_db()
    cur = conn.execute("DELETE FROM admin_unit1 WHERE code=?", (code,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Аймаг олдсонгүй")
    return jsonify(deleted=code)


# ===================== admin_unit2 (Сум / Дүүрэг) =====================
@app.route("/api/au2", methods=["GET"])
def list_au2():
    au1_code = request.args.get("au1_code")
    conn = get_db()
    if au1_code:
        rows = conn.execute(
            "SELECT * FROM admin_unit2 WHERE au1_code=? ORDER BY au2_code", (au1_code,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM admin_unit2 ORDER BY au2_code").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/au2/<au2_code>", methods=["GET"])
def get_au2(au2_code):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM admin_unit2 WHERE au2_code=?", (au2_code,)
    ).fetchone()
    conn.close()
    if not row:
        abort(404, description="Сум олдсонгүй")
    return jsonify(dict(row))


@app.route("/api/au2", methods=["POST"])
def create_au2():
    data = request.get_json(silent=True)
    require_fields(data, ["au2_code", "au2_name", "au1_code"])
    conn = get_db()
    parent = conn.execute(
        "SELECT 1 FROM admin_unit1 WHERE code=?", (data["au1_code"],)
    ).fetchone()
    if not parent:
        conn.close()
        abort(400, description="au1_code (эцэг аймаг) олдсонгүй")
    try:
        conn.execute(
            "INSERT INTO admin_unit2(au2_code, au2_name, au1_code) VALUES (?, ?, ?)",
            (data["au2_code"], data["au2_name"], data["au1_code"]),
        )
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ сумын код аль хэдийн бүртгэгдсэн байна")
    conn.close()
    return jsonify(data), 201


@app.route("/api/au2/<au2_code>", methods=["PUT"])
def update_au2(au2_code):
    data = request.get_json(silent=True)
    require_fields(data, ["au2_name"])
    conn = get_db()
    cur = conn.execute(
        "UPDATE admin_unit2 SET au2_name=? WHERE au2_code=?",
        (data["au2_name"], au2_code),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Сум олдсонгүй")
    return jsonify(au2_code=au2_code, au2_name=data["au2_name"])


@app.route("/api/au2/<au2_code>", methods=["DELETE"])
def delete_au2(au2_code):
    conn = get_db()
    cur = conn.execute("DELETE FROM admin_unit2 WHERE au2_code=?", (au2_code,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Сум олдсонгүй")
    return jsonify(deleted=au2_code)


# ===================== admin_unit3 (Баг / Хороо) =====================
@app.route("/api/au3", methods=["GET"])
def list_au3():
    au2_code = request.args.get("au2_code")
    au1_code = request.args.get("au1_code")
    conn = get_db()
    if au2_code:
        rows = conn.execute(
            "SELECT * FROM admin_unit3 WHERE au2_code=? ORDER BY au3_code", (au2_code,)
        ).fetchall()
    elif au1_code:
        rows = conn.execute(
            "SELECT * FROM admin_unit3 WHERE au1_code=? ORDER BY au3_code", (au1_code,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM admin_unit3 ORDER BY au3_code").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/au3/<au3_code>", methods=["GET"])
def get_au3(au3_code):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM admin_unit3 WHERE au3_code=?", (au3_code,)
    ).fetchone()
    conn.close()
    if not row:
        abort(404, description="Баг олдсонгүй")
    return jsonify(dict(row))


@app.route("/api/au3", methods=["POST"])
def create_au3():
    data = request.get_json(silent=True)
    require_fields(data, ["au3_code", "au3_name", "au1_code", "au2_code"])
    conn = get_db()
    parent = conn.execute(
        "SELECT au1_code FROM admin_unit2 WHERE au2_code=?", (data["au2_code"],)
    ).fetchone()
    if not parent:
        conn.close()
        abort(400, description="au2_code (эцэг сум) олдсонгүй")
    try:
        conn.execute(
            "INSERT INTO admin_unit3(au3_code, au3_name, au1_code, au2_code) "
            "VALUES (?, ?, ?, ?)",
            (data["au3_code"], data["au3_name"], data["au1_code"], data["au2_code"]),
        )
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ багийн код аль хэдийн бүртгэгдсэн байна")
    conn.close()
    return jsonify(data), 201


@app.route("/api/au3/<au3_code>", methods=["PUT"])
def update_au3(au3_code):
    data = request.get_json(silent=True)
    require_fields(data, ["au3_name"])
    conn = get_db()
    cur = conn.execute(
        "UPDATE admin_unit3 SET au3_name=? WHERE au3_code=?",
        (data["au3_name"], au3_code),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Баг олдсонгүй")
    return jsonify(au3_code=au3_code, au3_name=data["au3_name"])


@app.route("/api/au3/<au3_code>", methods=["DELETE"])
def delete_au3(au3_code):
    conn = get_db()
    cur = conn.execute("DELETE FROM admin_unit3 WHERE au3_code=?", (au3_code,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Баг олдсонгүй")
    return jsonify(deleted=au3_code)


# ===================== school_category (Сургуулийн ангилал) =====================
SCHOOL_CATEGORY_FIELDS = ("buten_ner", "tovch_ner", "angli_ner")


@app.route("/api/school_category", methods=["GET"])
def list_school_category():
    conn = get_db()
    rows = conn.execute("SELECT * FROM school_category ORDER BY id").fetchall()
    conn.close()
    return jsonify(rows_to_list(rows))


@app.route("/api/school_category/<int:cid>", methods=["GET"])
def get_school_category(cid):
    conn = get_db()
    row = conn.execute("SELECT * FROM school_category WHERE id=?", (cid,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(dict(row))


@app.route("/api/school_category", methods=["POST"])
def create_school_category():
    data = request.get_json(silent=True)
    require_fields(data, ["buten_ner"])
    # id заавал биш — өгвөл тогтсон утгаар, эс бөгөөс автоматаар оноогдоно
    cols, vals = [], []
    if data.get("id") is not None:
        cols.append("id")
        vals.append(data["id"])
    for f in SCHOOL_CATEGORY_FIELDS:
        cols.append(f)
        vals.append(data.get(f))
    ph = ", ".join("?" * len(cols))
    conn = get_db()
    try:
        cur = conn.execute(
            f"INSERT INTO school_category({', '.join(cols)}) VALUES ({ph})", vals)
        conn.commit()
    except Exception:
        conn.close()
        abort(409, description="Энэ id аль хэдийн бүртгэгдсэн байна")
    new_id = data.get("id") or cur.lastrowid
    row = conn.execute("SELECT * FROM school_category WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201


@app.route("/api/school_category/<int:cid>", methods=["PUT"])
def update_school_category(cid):
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="JSON их бие шаардлагатай")
    fields = [f for f in SCHOOL_CATEGORY_FIELDS if f in data]
    if not fields:
        abort(400, description="Шинэчлэх талбар алга")
    sets = ", ".join(f"{f}=?" for f in fields)
    vals = [data[f] for f in fields] + [cid]
    conn = get_db()
    cur = conn.execute(f"UPDATE school_category SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(updated=cid, fields=fields)


@app.route("/api/school_category/<int:cid>", methods=["DELETE"])
def delete_school_category(cid):
    conn = get_db()
    cur = conn.execute("DELETE FROM school_category WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, description="Ангилал олдсонгүй")
    return jsonify(deleted=cid)


if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', debug=True, port=5001)
