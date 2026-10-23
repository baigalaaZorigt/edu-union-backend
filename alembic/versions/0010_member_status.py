"""member_status лавлах + member.status_id (хуучин status текстийг тааруулж шилжүүлнэ)

1. member_status (id, code, name — хоёул UNIQUE) + 4 суурь мөр: Гишүүн, Дарга, Тэргүүлэгч, Сонгуульт.
2. member.status_id (FK → member_status.id, ON DELETE RESTRICT, nullable).
3. Хуучин member.status текстийг том/жижиг үсэг үл харгалзан (`_match`) тааруулна — таарвал
   status_id бөглөгдөнө, ТЕКСТ ӨӨРЧЛӨГДӨХГҮЙ (API status_id-тай мөрөнд status = status_name
   буцаана). Таарахгүй ("Багш", "0014", "Боловсрол" ...) нь status_id = NULL.
4. member_status.* эрхүүдийг үүсгээд read-ийг Super Admin (role.code='1') ба Зөвлөх мэргэжилтэн
   дүрд НЭГ УДАА онооно (admin дүр seed_users()-ээр бүгдийг авна). Дараа нь админ хасаж болно.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-23
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

STATUSES = (("01", "Гишүүн"), ("02", "Дарга"), ("03", "Тэргүүлэгч"), ("04", "Сонгуульт"))
# Ойролцоо утгыг аль статуст холбох (ДАРААЛЛААР — эхний таарсан нь):
#   "Тэргүүлэгч, хорооны дарга" -> Тэргүүлэгч (дарга гэдгээс өмнө шалгана)
#   "Зөвлөлийн/Бүлгийн/ҮЭ-ийн бүлгийн/ҮЭ-ийн хорооны дарга", "дарга" -> Дарга
#   "гишүүн", "ҮЭ-ийн гишүүн" -> Гишүүн
KEYWORDS = (("тэргүүлэгч", "Тэргүүлэгч"), ("сонгуульт", "Сонгуульт"),
            ("дарга", "Дарга"), ("гишүүн", "Гишүүн"))
SPECIALIST_ROLE = "зөвлөх мэргэжилтэн"
ACTIONS = (("create", "нэмэх"), ("read", "харах"), ("update", "засах"), ("delete", "устгах"))


def _norm(value):
    return " ".join(str(value or "").split()).casefold()


def _match(text):
    """Хуучин status текст -> member_status-ийн нэр (эсвэл None)."""
    t = _norm(text)
    if not t:
        return None
    for _, name in STATUSES:
        if t == _norm(name):
            return name
    for word, name in KEYWORDS:
        if word in t:
            return name
    return None


def upgrade():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ms = op.create_table(
        "member_status",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.Text),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text),
        sa.Column("updated_at", sa.Text),
        sa.Column("deleted_at", sa.Text),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("app_user.id", ondelete="SET NULL")),
        sa.UniqueConstraint("code", name="member_status_code_key"),
        sa.UniqueConstraint("name", name="member_status_name_key"),
        sqlite_autoincrement=True,
    )
    op.add_column("member", sa.Column(
        "status_id", sa.Integer, sa.ForeignKey("member_status.id", ondelete="RESTRICT")),
        inline_references=True)      # SQLite: ADD CONSTRAINT байхгүй тул REFERENCES-ийг мөрд нь
    op.create_index("idx_member_status_id", "member", ["status_id"])

    conn = op.get_bind()
    conn.execute(ms.insert(), [{"code": c, "name": n, "created_at": now, "updated_at": now}
                               for c, n in STATUSES])
    ids = {r.name: r.id for r in conn.execute(sa.select(ms.c.id, ms.c.name))}

    member = sa.table("member", sa.column("id", sa.Integer), sa.column("status", sa.Text),
                      sa.column("status_id", sa.Integer))
    by_status = {}
    for r in conn.execute(sa.select(member.c.id, member.c.status)
                          .where(member.c.status.is_not(None))):
        name = _match(r.status)
        if name:
            by_status.setdefault(ids[name], []).append(r.id)
    for sid, mids in by_status.items():
        for i in range(0, len(mids), 500):
            conn.execute(member.update().where(member.c.id.in_(mids[i:i + 500]))
                         .values(status_id=sid))

    _grant_read(conn)


def _grant_read(conn):
    perm = sa.table("permission", sa.column("id", sa.Integer), sa.column("code", sa.Text),
                    sa.column("name", sa.Text), sa.column("resource", sa.Text),
                    sa.column("action", sa.Text))
    role = sa.table("role", sa.column("id", sa.Integer), sa.column("name", sa.Text),
                    sa.column("code", sa.Text), sa.column("deleted_at", sa.Text))
    rp = sa.table("role_permission", sa.column("role_id", sa.Integer),
                  sa.column("permission_id", sa.Integer))
    have = set(conn.scalars(sa.select(perm.c.code).where(perm.c.resource == "member_status")))
    fresh = [{"code": f"member_status.{a}", "name": f"Гишүүний статус {label}",
              "resource": "member_status", "action": a}
             for a, label in ACTIONS if f"member_status.{a}" not in have]
    if fresh:
        conn.execute(perm.insert(), fresh)
    pid = conn.scalar(sa.select(perm.c.id).where(perm.c.code == "member_status.read"))
    roles = [r.id for r in conn.execute(sa.select(role.c.id, role.c.name, role.c.code)
                                        .where(role.c.deleted_at.is_(None)))
             if _norm(r.name) == SPECIALIST_ROLE or str(r.code or "").strip() == "1"]
    granted = set(conn.scalars(sa.select(rp.c.role_id).where(rp.c.permission_id == pid)))
    rows = [{"role_id": rid, "permission_id": pid} for rid in roles if rid not in granted]
    if rows:
        conn.execute(rp.insert(), rows)


def downgrade():
    op.drop_index("idx_member_status_id", "member")
    with op.batch_alter_table("member") as batch:     # SQLite-д DROP COLUMN batch-аар
        batch.drop_column("status_id")
    op.drop_table("member_status")
