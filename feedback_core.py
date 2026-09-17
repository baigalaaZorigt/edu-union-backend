"""Санал хүсэлт, Өргөдөл гомдлын хуваалцсан цөм (admin + client site хоёулаа).

Хүснэгтүүд (db.py-ийн SCHEMA_FEEDBACK):
    suggestions (Санал хүсэлт) , complaints (Өргөдөл, гомдол)

Энэ модуль нь ЗӨВХӨН домэйний логик: шалгалт, хуудаслалт, цэвэр хэлбэр (public_*).
HTTP маршрутууд нь:
    client/feedback.py — POST /api/portal/suggestions|complaints  (ТОКЕНГҮЙ — маягт илгээх)
    admin/feedback.py  — GET|DELETE /api/admin/suggestions|complaints

Хоёр маягт бүтцээрээ бараг ижил (ялгаа нь текстийн багана + хавсралт) тул
`KINDS`-ээр параметрлэж, жагсаалт/устгал/шалгалтыг ЗӨВХӨН нэг удаа бичив —
эс бөгөөс 6 маршрут хоёр дахин давхардах байсан.
"""
import re
from datetime import datetime, timezone

from flask import abort

MAX_PER_PAGE = 100                    # хуудаслалтын дээд хэмжээ (forms/news-тэй ижил)

# Маягтын төрөл (URL-ийн хэсэг = хүснэгтийн нэр) -> тодорхойлолт.
#   required — заавал бөглөх талбарууд (спек §5)
#   optional — заавал биш (зөвхөн хавсралт)
#   search   — ?search= аль баганаар хайхыг заана
KINDS = {
    "suggestions": {
        "table": "suggestions",
        "required": ("name", "email", "phone", "message"),
        "optional": (),
        "search": ("name", "email", "phone", "message"),
        "label": "Санал хүсэлт",
        "ok_message": "Таны санал хүсэлт бүртгэгдлээ.",
    },
    "complaints": {
        "table": "complaints",
        "required": ("name", "email", "phone", "description"),
        "optional": ("file_url", "file_name"),
        "search": ("name", "email", "phone", "description"),
        "label": "Өргөдөл, гомдол",
        "ok_message": "Таны өргөдөл, гомдол бүртгэгдлээ.",
    },
}

# V1-д төлөв нь ЗӨВХӨН 'new' — солих маршрут спект байхгүй (§2-ыг үзнэ үү),
# багана нь ирээдүйд "шинэ / хянасан" гэж харуулахад бэлэн байхын тулд л бий.
STATUSES = ("new", "reviewed")

# Талбарын дээд урт — спекийн VARCHAR(...)-тай тохирно. SQLite урт хязгаарлахгүй
# тул кодоор шалгана (Postgres дээр ч 400 нь 500-аас сайн).
MAX_LEN = {"name": 200, "email": 255, "phone": 20, "file_name": 255, "file_url": 2000}

# И-мэйлийн хэлбэр — "a@b.cd" (RFC бус, практик шалгалт)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
# Утсыг шалгахын ТУЛД цэвэрлэх тэмдэгтүүд (хадгалахдаа хэрэглэгчийн бичсэнээр нь)
_PHONE_TRIM_RE = re.compile(r"[\s()\-]")
PHONE_DIGITS = 8                      # Монголын дугаар — 8 орон (+976 угтвар зөвшөөрнө)


def now_str():
    """Одоогийн UTC цаг — "YYYY-MM-DD HH:MM:SS".

    forms_core / news_core-той ижил хэлбэр (спекийн created_at жишээ ч ийм).
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def bad(conn, message, code=400):
    """Холболтыг хааж байгаад алдаа шидэнэ (холболт алдагдахаас сэргийлнэ)."""
    if conn is not None:
        conn.close()
    abort(code, description=message)


def _text(value):
    """Ирсэн утгыг цэвэр текст болгоно (текст биш бол None)."""
    return value.strip() if isinstance(value, str) else None


def check_phone(value):
    """Утасны дугаар Монголын 8 оронтой эсэх (+976 / 976 угтвар зөвшөөрнө)."""
    digits = _PHONE_TRIM_RE.sub("", value)
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("976"):
        digits = digits[3:]
    return digits.isdigit() and len(digits) == PHONE_DIGITS


def validate(conn, kind, data):
    """Маягтын их биеийг шалгаад, хадгалахад бэлэн dict буцаана (зөрвөл 400).

    Заавал талбар дутуу/хоосон, и-мэйлийн хэлбэр, утасны урт, талбарын дээд
    урт — бүгд 400. (Спек §5. Энэ репо хаа сайгүй 400 буцаадаг; 422-г зөвхөн
    нууц үг солих үед хэрэглэдэг.)
    """
    spec = KINDS[kind]
    if not isinstance(data, dict):
        bad(conn, "JSON их бие шаардлагатай")

    out = {}
    missing = []
    for f in spec["required"]:
        val = _text(data.get(f))
        if not val:
            missing.append(f)
        out[f] = val
    if missing:
        bad(conn, "Дутуу талбар: " + ", ".join(missing))

    if not _EMAIL_RE.match(out["email"]):
        bad(conn, "И-мэйл хаяг буруу байна")
    if not check_phone(out["phone"]):
        bad(conn, f"Утасны дугаар буруу байна ({PHONE_DIGITS} оронтой байх ёстой)")

    for f in spec["optional"]:
        out[f] = _text(data.get(f)) or None

    for f, limit in MAX_LEN.items():
        if out.get(f) and len(out[f]) > limit:
            bad(conn, f"{f} нь {limit} тэмдэгтээс урт байж болохгүй")

    return out


def insert(conn, kind, values):
    """Шалгагдсан утгуудыг хүснэгтэд нэмж, шинэ мөрийн id-г буцаана."""
    spec = KINDS[kind]
    now = now_str()
    cols = list(values)
    params = [values[c] for c in cols]
    # status нь ҮРГЭЛЖ 'new' (V1), огноог форматтай нь өөрсдөө бичнэ — хүснэгтийн
    # INSERT trigger нь COALESCE тул бичсэн утга ялна (CLAUDE.md-ийн зарчим).
    cols += ["status", "created_at", "updated_at"]
    params += ["new", now, now]
    ph = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO {spec['table']}({', '.join(cols)}) VALUES ({ph})", params)
    conn.commit()
    return cur.lastrowid


def public_row(kind, row):
    """Мөрийг спекийн §4 хэлбэрээр буцаана (updated_at нь гадагшаа хэрэггүй)."""
    spec = KINDS[kind]
    out = {"id": row["id"]}
    for f in spec["required"] + spec["optional"]:
        out[f] = row[f]
    out["status"] = row["status"]
    out["created_at"] = row["created_at"]
    return out


def list_page(conn, kind, args):
    """Жагсаалт + хуудаслалт: {items, page, pages, per_page, total} (спек §4).

    `args` нь request.args (эсвэл ижил `.get`-тэй mapping). Шүүлтүүр:
    ?search= (нэр/и-мэйл/утас/текстээр), ?page=, ?per_page=. Шинэ нь дээрээ
    (ORDER BY id DESC) — админы жагсаалт хамгийн сүүлийн хүсэлтээс эхэлнэ.
    """
    spec = KINDS[kind]
    where, params = [], []
    search = (args.get("search") or "").strip()
    if search:
        where.append("(" + " OR ".join(f"{c} LIKE ?" for c in spec["search"]) + ")")
        params += [f"%{search}%"] * len(spec["search"])
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) FROM {spec['table']}{clause}", params).fetchone()[0]
    try:
        page = max(1, int(args.get("page", 1)))
        per_page = min(MAX_PER_PAGE, max(1, int(args.get("per_page", 20))))
    except (TypeError, ValueError):
        bad(conn, "page / per_page нь тоо байх ёстой")
    data = conn.execute(
        f"SELECT * FROM {spec['table']}{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page]).fetchall()
    items = [public_row(kind, r) for r in data]
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": (total + per_page - 1) // per_page}
