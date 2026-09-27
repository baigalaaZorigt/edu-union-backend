"""Excel экспорт — гишүүд ба байгууллагууд.

    GET /api/member/export        — GET /api/member-тэй ИЖИЛ шүүлт + хамрах хүрээ (member.read)
    GET /api/organization/export  — GET /api/organization-тэй ИЖИЛ (organization.read)

Хуудаслалтгүй — шүүлтэд таарсан бүх мөр файлд орно. Query-г жагсаалтын маршрутаас
(member_list_query / org_list_query) авдаг тул файл дэлгэцийн жагсаалтаас зөрөхгүй.
Эрх нь auth.py-ийн ердийн дүрмээр: замын эхний сегмент (member / organization) + GET = read.
"""
from sqlalchemy import select

from core.orm import session
from core.orm.models import Contact
from core.xlsx import Sheet, as_date, xlsx_response

from admin.union import bp
from admin.union.member import member_list_query, member_row
from admin.union.organization import org_list_query, org_row, org_stats_many

MEMBER_HEADERS = ["№", "Овог нэр", "Төрсөн он", "Хүйс", "Регистрийн дугаар",
                  "ҮЭ-ийн бүртгэлийн дугаар", "ҮЭ-д элссэн огноо", "ҮЭ-ийн гишүүний статус",
                  "Статус", "Албан тушаал", "Мэргэжил", "Утасны дугаар", "Байгууллага"]
ORG_HEADERS = ["№", "Код", "Нэр", "Төрөл", "Регистрийн дугаар", "Удирдлагын мэдээлэл",
               "Утас1", "Утас2", "И-мэйл", "Гишүүдийн тоо", "Эмэгтэй гишүүд",
               "35 хүртэлх насны гишүүд"]
CHUNK = 500                        # IN (...) параметрийн тоог хязгаарлах


def _member_phones():
    """Гишүүн бүрийн утас/факс (contact хүснэгт) — "99112233, 70112233" хэлбэрээр."""
    out = {}
    for r in session().execute(
            select(Contact.owner_id, Contact.value)
            .where(Contact.owner_type == "member", Contact.type.in_(("утас", "факс")))
            .order_by(Contact.id)):
        out.setdefault(r.owner_id, []).append(r.value)
    return {k: ", ".join(v) for k, v in out.items()}


def _full_name(m):
    return " ".join(x for x in (m["last_name"], m["first_name"]) if x) or None


def _member_rows(members, phones):
    for i, m in enumerate(members, start=1):
        born = as_date(m["birth_date"])
        yield [i, _full_name(m), born.year if born else None, m["gender"], m["register_number"],
               m["union_card_number"], as_date(m["union_joined_date"]), m["member_status"],
               m["status"], m["position_name"], m["profession_name"], phones.get(m["id"]),
               m["organization_name"]]


@bp.route("/api/member/export", methods=["GET"])
def export_members():
    members = [member_row(m) for m in session().execute(member_list_query()).mappings()]
    phones = _member_phones()
    return xlsx_response("гишүүд", [Sheet("Гишүүд", MEMBER_HEADERS,
                                          _member_rows(members, phones))])


def _org_rows(orgs, stats):
    for i, o in enumerate(orgs, start=1):
        s = stats[o["id"]]
        yield [i, o["full_code"], o["name"], o["school_category_short_name"],
               o["registration_number"], o["contact_name"], o["phone1"], o["phone2"], o["email"],
               s["total_members"], s["female_members"], s["under35_members"]]


@bp.route("/api/organization/export", methods=["GET"])
def export_organizations():
    orgs = [org_row(o) for o in session().execute(org_list_query()).mappings()]
    ids = [o["id"] for o in orgs]
    stats = {}
    for i in range(0, len(ids), CHUNK):
        stats.update(org_stats_many(ids[i:i + CHUNK]))
    return xlsx_response("байгууллагууд", [Sheet("Байгууллагууд", ORG_HEADERS,
                                                  _org_rows(orgs, stats))])
