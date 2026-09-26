"""member (Гишүүн) — CRUD, эвлэлийн картын дугаар, хамрах хүрээ."""

from flask import jsonify, request, abort

from core.db import get_db
from core.helpers import fail, json_body, pick, require, rows
from core.scope_core import member_condition, require_org_in_scope, require_member_in_scope

from admin.union import bp
from admin.union.common import (CARD_CODE_LEN, MEMBER_REWARD_SELECT, ORG_FULL_CODE_SQL,
                                _check_au, _check_ref, _create, _delete_by_id, _digit_code,
                                _org_full_code, _purge_orphan_contacts, _purge_orphan_files,
                                _require_row, _update_by_id, _where)


# Гишүүний бүртгэлийн талбарууд (organization_id-аас бусад, оруулж/засаж болох).
# Боловсрол (#10) нь member_education, утас/факс (#11) нь contact хүснэгтэд
# (owner_type='member') олноор бүртгэгдэнэ.
# union_card_number энд БАЙХГҮЙ — тэр нь union_card_code-оос автоматаар бүрдэнэ.
MEMBER_FIELDS = (
    "last_name", "first_name", "birth_date", "gender", "register_number",
    "union_card_code", "union_joined_date", "member_status", "status",
    "position_id", "profession_id", "salary_scale_id", "email",
    "au1_code", "au2_code", "au3_code", "address_detail", "signature", "is_active",
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
NOT_FOUND = "Гишүүн олдсонгүй"


def _card_number(conn, org_id, card_code):
    """Гишүүний 9 оронтой батламжийн дугаар = байгууллагын 5 орон + гишүүний 4 орон."""
    full = _org_full_code(conn, org_id)
    if not full:
        fail(conn, 400, "Байгууллагад сургуулийн ангилал ба 3 оронтой код (org_code) "
                        "тохируулаагүй тул батламжийн дугаар үүсгэх боломжгүй")
    return full + card_code


def _check_card_unique(conn, card_number, member_id=None):
    """Батламжийн 9 оронтой дугаар давхардаж байвал 409."""
    sql = "SELECT id FROM member WHERE union_card_number=?"
    params = [card_number]
    if member_id is not None:
        sql += " AND id<>?"
        params.append(member_id)
    if conn.execute(sql, params).fetchone():
        fail(conn, 409, f"Батламжийн дугаар {card_number} аль хэдийн бүртгэгдсэн байна")


def _validate_member(data):
    """Гишүүний JSON-ы энгийн шалгалт (DB холболт нээхээс ӨМНӨ дуудна).

    - member_status / status: лавлахгүй, гараас бичих ЧӨЛӨӨТ ТЕКСТ
    - union_card_code: яг 4 оронтой тоо (энэ нь union_card_number-ийн сүүлийн 4 орон)
    - is_active / signature: зөвхөн 0 эсвэл 1 (true/false-ыг хөрвүүлнэ)
    """
    for flag in ("is_active", "signature"):
        val = data.get(flag)
        if val is None:
            continue
        if not (isinstance(val, bool) or val in (0, 1, "0", "1")):
            abort(400, description=f"{flag} нь 0 эсвэл 1 байна")
        data[flag] = int(val)
    for field in ("member_status", "status"):
        st = data.get(field)
        if st is not None and (not isinstance(st, str) or not st.strip()):
            abort(400, description=f"{field} зөвхөн текст байна (ж: 'идэвхтэй')")
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
    conn = get_db()
    # Хамрах хүрээ — гишүүн нь харьяа байгууллагаараа дамжин шүүгдэнэ (спек §5)
    scope_cond, scope_params = member_condition(conn, alias="m")
    if scope_cond:
        cond.append(scope_cond)
        params += scope_params
    data = rows(conn.execute(
        MEMBER_SELECT + _where(cond) + " ORDER BY m.id", params).fetchall())
    conn.close()
    return jsonify(data)


@bp.route("/api/member/<int:mid>", methods=["GET"])
def get_member(mid):
    conn = get_db()
    require_member_in_scope(conn, mid)
    row = conn.execute(MEMBER_SELECT + " WHERE m.id=?", (mid,)).fetchone()
    if not row:
        fail(conn, 404, NOT_FOUND)
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
    _require_row(conn, "organization", data["organization_id"],
                 "organization_id (эцэг байгууллага) олдсонгүй")
    require_org_in_scope(conn, data["organization_id"])
    _member_refs(conn, data)
    _check_au(conn, data)
    values = {"organization_id": data["organization_id"],
              **pick(data, MEMBER_FIELDS, skip_none=True)}
    # 4 оронтой код өгсөн бол 9 оронтой батламжийн дугаарыг үүсгэнэ
    if data.get("union_card_code") is not None:
        card = _card_number(conn, data["organization_id"], data["union_card_code"])
        _check_card_unique(conn, card)
        values["union_card_number"] = card
    return _create(conn, "member", values, MEMBER_SELECT + " WHERE m.id=?")


@bp.route("/api/member/<int:mid>", methods=["PUT", "PATCH"])
def update_member(mid):
    data = json_body()
    _validate_member(data)
    values = pick(data, MEMBER_FIELDS)
    if not values:
        abort(400, description="Шинэчлэх талбар алга")
    conn = get_db()
    require_member_in_scope(conn, mid)
    _member_refs(conn, data)
    _check_au(conn, data)
    # 4 оронтой кодыг сольсон бол 9 оронтой дугаарыг дахин үүсгэнэ
    if data.get("union_card_code") is not None:
        row = conn.execute("SELECT organization_id FROM member WHERE id=?", (mid,)).fetchone()
        if not row:
            fail(conn, 404, NOT_FOUND)
        card = _card_number(conn, row["organization_id"], data["union_card_code"])
        _check_card_unique(conn, card, mid)
        values["union_card_number"] = card
    return _update_by_id(conn, "member", mid, values, NOT_FOUND)


@bp.route("/api/member/<int:mid>", methods=["DELETE"])
def delete_member(mid):
    conn = get_db()
    require_member_in_scope(conn, mid)
    return _delete_by_id(conn, "member", mid, NOT_FOUND,
                         _purge_orphan_contacts, _purge_orphan_files)
