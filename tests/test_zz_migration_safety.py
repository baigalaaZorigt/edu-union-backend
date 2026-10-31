"""Migration-ий аюулгүй байдал — production-ий өгөгдөл, багана устахгүй / өөрчлөгдөхгүй.

Production (RDS) дээр push бүр `alembic upgrade head` ажиллуулдаг тул шинэ revision:
  * хүснэгт, багана устгах / нэр солих / төрөл өөрчлөх ёсгүй (downgrade()-д л болно);
  * өмнө байсан мөрийг устгах, өмнө байсан баганын утгыг өөрчлөх ёсгүй — шинэ хүснэгт,
    шинэ багана, шинэ мөр (seed, эрх) нэмэх нь зөв.

1. Статик: revision файл бүрийн downgrade()-ээс бусад кодонд устгах op / SQL байхгүй.
2. Динамик: энэ pytest session-ий өгөгдөлтэй DB-г (seed + өмнөх тестүүдийн мөр, soft delete
   хийсэн мөр) ХУУЛЖ, START хүртэл downgrade хийгээд revision бүрийг нэг нэгээр upgrade хийнэ;
   алхам бүрийн өмнө/дараа хүснэгт, багана, мөр (PK-аар), хуучин баганын утгыг харьцуулна.
   Файлын нэр `zz` — бусад тест өгөгдөл бичсэний дараа ажиллана.

Санаатай өгөгдөл шилжүүлэлт хэрэгтэй бол ALLOWED_CHANGES-д (revision, хүснэгт, багана) нэмж,
яагаад гэдгийг тайлбарла — тэгэхгүй бол тест унана.
"""
import ast
import os
import re
import shutil

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, table, column

from core import db

VERSIONS = os.path.join(db.BASE_DIR, "alembic", "versions")
START = "0004"                 # эндээс хойшхи revision бүрийг өгөгдөлтэй DB дээр шалгана

# Хүснэгт/багана устгах, нэр/төрөл солих — зөвхөн downgrade()-д зөвшөөрнө
FORBIDDEN_OPS = {"drop_table", "drop_column", "drop_constraint", "alter_column",
                 "rename_table", "delete"}
FORBIDDEN_SQL = re.compile(r"\b(DROP\s+(TABLE|COLUMN)|DELETE\s+FROM|TRUNCATE|"
                           r"ALTER\s+TABLE\s+\S+\s+(DROP|RENAME|ALTER))\b")
# Production-д аль хэдийн хэрэгжсэн, хуучин схемийг өвлөсөн revision-ууд
STATIC_EXEMPT = {"0001"}
# (revision, хүснэгт, багана) — хуучин мөрийн утгыг САНААТАЙ өөрчилдөг шилжүүлэлт.
# АНХААР: Postgres-д хуучин хүснэгтийн мөрийг UPDATE хийвэл timestamp trigger updated_at-ийг
# migration ажилласан цагаар солино (SQLite-д ийм trigger байхгүй тул зөвхөн --pg барина).
ALLOWED_CHANGES = {
    # 0010 status_id-г бөглөхөд PG trigger таарсан гишүүдийн updated_at-ийг шинэчилсэн —
    # production-д аль хэдийн хэрэгжсэн, өгөгдөл алдагдаагүй.
    ("0010", "member", "updated_at"),
}


def _revisions():
    for name in sorted(os.listdir(VERSIONS)):
        if re.match(r"^\d{4}_.*\.py$", name):
            yield name[:4], os.path.join(VERSIONS, name)


@pytest.mark.parametrize("rev, path", list(_revisions()))
def test_upgrade_code_has_no_destructive_ops(rev, path):
    if rev in STATIC_EXEMPT:
        pytest.skip("хуучин baseline")
    tree = ast.parse(open(path, encoding="utf-8").read())
    found = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                name = getattr(n.func, "attr", getattr(n.func, "id", ""))
                if name in FORBIDDEN_OPS:
                    found.append(f"{name}() мөр {n.lineno}")
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and FORBIDDEN_SQL.search(n.value):
                found.append(f"SQL «{FORBIDDEN_SQL.search(n.value).group(0)}» мөр {n.lineno}")
    assert not found, f"{rev}: upgrade талд устгах үйлдэл — " + ", ".join(found)


# ------------------------------- динамик -------------------------------
def snapshot(conn):
    """{хүснэгт: (баганууд, {pk: {багана: утга}})} — alembic_version-оос бусад."""
    insp = inspect(conn)
    out = {}
    for name in insp.get_table_names():
        if name == "alembic_version":
            continue
        cols = [c["name"] for c in insp.get_columns(name)]
        pk = insp.get_pk_constraint(name)["constrained_columns"] or cols
        t = table(name, *(column(c) for c in cols))
        rows = {}
        for r in conn.execute(select(t)).mappings():
            rows[tuple(r[c] for c in pk)] = dict(r)
        out[name] = (cols, rows)
    return out


def compare(before, after, rev):
    """Хуучин бүх хүснэгт / багана / мөр / утга хэвээр эсэх -> алдааны жагсаалт."""
    problems = []
    for name, (cols, rows) in before.items():
        if name not in after:
            problems.append(f"хүснэгт устсан: {name}")
            continue
        new_cols, new_rows = after[name]
        problems += [f"багана устсан: {name}.{c}" for c in cols if c not in new_cols]
        lost = [k for k in rows if k not in new_rows]
        if lost:
            problems.append(f"{name}: {len(lost)} мөр устсан (ж: {lost[:3]})")
        for key, row in rows.items():
            if key not in new_rows:
                continue
            for c in cols:
                if c in new_cols and (rev, name, c) not in ALLOWED_CHANGES \
                        and row[c] != new_rows[key][c]:
                    problems.append(f"{name}.{c} (pk {key}) өөрчлөгдсөн: "
                                    f"{row[c]!r} -> {new_rows[key][c]!r}")
                    break
    return problems


def _cfg(conn):
    cfg = Config(os.path.join(db.BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(db.BASE_DIR, "alembic"))
    cfg.attributes["connection"] = conn
    return cfg


def check_chain(url, start=START):
    """url-ийн DB-г start хүртэл downgrade хийж, revision бүрийг шалгана -> {rev: алдаанууд}."""
    script = ScriptDirectory.from_config(_cfg(None))
    chain = [r.revision for r in script.walk_revisions(f"{start}", "heads")][::-1]
    chain = [r for r in chain if r != start]
    eng = create_engine(url)
    report = {}
    try:
        with eng.begin() as conn:
            command.downgrade(_cfg(conn), start)
        for rev in chain:
            with eng.begin() as conn:
                before = snapshot(conn)
                command.upgrade(_cfg(conn), rev)
                report[rev] = compare(before, snapshot(conn), rev)
    finally:
        eng.dispose()
    return report


def test_each_migration_keeps_existing_data(api, tmp_path):
    api.get("/api/member")                       # session DB бүрэн үүссэн байг
    copy = tmp_path / "copy.db"
    shutil.copy(db.DB_PATH, copy)
    report = check_chain(f"sqlite:///{copy}")
    assert report, "шалгах revision олдсонгүй"
    bad = {rev: p for rev, p in report.items() if p}
    assert not bad, "\n".join(f"{rev}: {'; '.join(p[:5])}" for rev, p in bad.items())



def test_checker_catches_destructive_changes(tmp_path):
    """Шалгагч өөрөө ажилладаг эсэх: мөр устгах, багана/хүснэгт устгах, утга солихыг барина."""
    eng = create_engine(f"sqlite:///{tmp_path / 'x.db'}")
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE a (id INTEGER PRIMARY KEY, name TEXT, note TEXT)")
        c.exec_driver_sql("CREATE TABLE b (id INTEGER PRIMARY KEY)")
        c.exec_driver_sql("INSERT INTO a VALUES (1, 'x', 'n'), (2, 'y', 'n')")
        before = snapshot(c)
        c.exec_driver_sql("DELETE FROM a WHERE id = 2")
        c.exec_driver_sql("UPDATE a SET name = 'z' WHERE id = 1")
        c.exec_driver_sql("ALTER TABLE a DROP COLUMN note")
        c.exec_driver_sql("DROP TABLE b")
        c.exec_driver_sql("CREATE TABLE c (id INTEGER PRIMARY KEY)")     # шинэ хүснэгт — зөв
        problems = compare(before, snapshot(c), "9999")
    eng.dispose()
    text = " | ".join(problems)
    assert "хүснэгт устсан: b" in text and "багана устсан: a.note" in text
    assert "a: 1 мөр устсан" in text and "a.name (pk (1,)) өөрчлөгдсөн" in text
    assert len(problems) == 4
