"""SQLite (`admin_units.db`) -> Postgres рүү өгөгдлийг зөөнө.

Ажиллуулах:
    DATABASE_URL="postgresql://хэрэглэгч:нууц@хост:5432/eduunion" python migrate_to_pg.py

Юу хийдэг:
  1. Postgres дээр бүтцийг үүсгэнэ (`db.init_db()` — идемпотент).
  2. Хүснэгтүүдийг FK-ийн дарааллаар (эцэг нь эхэлж) эрэмбэлээд мөрүүдийг хуулна.
  3. IDENTITY дарааллуудыг хамгийн том id-д тааруулна (дараагийн INSERT давхцахгүй).
  4. Эх ба хүлээн авагчийн мөрийн тоог тулгаж хэвлэнэ.

Идемпотент: мөр бүрийг `ON CONFLICT DO NOTHING`-оор оруулдаг тул дахин
ажиллуулахад давхардахгүй. `--truncate` өгвөл эхлээд бүх хүснэгтийг цэвэрлэнэ.
"""
import os
import sqlite3
import sys

import db

SKIP_TABLES = {"sqlite_sequence"}


def sqlite_tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name")]


def pg_fk_edges(pg):
    """{хүснэгт: {эцэг хүснэгтүүд}} — FK-ийн хамаарал."""
    rows = pg.execute("""
        SELECT tc.table_name, ccu.table_name AS parent
          FROM information_schema.table_constraints tc
          JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
         WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    """).fetchall()
    edges = {}
    for r in rows:
        if r["table_name"] != r["parent"]:          # өөрөө өөр рүүгээ (menu.parent_id)
            edges.setdefault(r["table_name"], set()).add(r["parent"])
    return edges


def order_tables(tables, edges):
    """Эцэг хүснэгт нь эхэлж орох дараалал (энгийн топологи эрэмбэлэлт)."""
    done, out = set(), []
    todo = list(tables)
    while todo:
        moved = False
        for t in list(todo):
            if edges.get(t, set()) - done - {t} <= set():
                out.append(t)
                done.add(t)
                todo.remove(t)
                moved = True
        if not moved:                      # тойрог хамаарал — үлдсэнийг нь хэвээр
            out += todo
            break
    return out


def main():
    if not db.IS_PG:
        sys.exit("DATABASE_URL тохируулаагүй байна — зөөх хүлээн авагч алга.")
    if not os.path.exists(db.DB_PATH):
        sys.exit(f"SQLite файл олдсонгүй: {db.DB_PATH}")

    print("1) Postgres дээр бүтэц үүсгэж байна ...")
    db.init_db()

    src = sqlite3.connect(db.DB_PATH)
    src.row_factory = sqlite3.Row
    pg = db.get_db()

    tables = [t for t in sqlite_tables(src) if t not in SKIP_TABLES]
    ordered = order_tables(tables, pg_fk_edges(pg))

    if "--truncate" in sys.argv:
        print("2) Хүлээн авагчийг цэвэрлэж байна (--truncate) ...")
        pg.execute("TRUNCATE " + ", ".join(ordered) + " RESTART IDENTITY CASCADE")
        pg.commit()

    print("2) Мөрүүдийг хуулж байна ...")
    report = []
    for t in ordered:
        src_cols = [r[1] for r in src.execute(f"PRAGMA table_info({t})")]
        dst_cols = [r["column_name"] for r in pg.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=?", (t,)).fetchall()]
        cols = [c for c in src_cols if c in dst_cols]
        if not cols:
            continue
        rows = src.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()
        if rows:
            ph = ", ".join("?" * len(cols))
            pg.executemany(
                f"INSERT INTO {t}({', '.join(cols)}) VALUES ({ph}) ON CONFLICT DO NOTHING",
                [tuple(r) for r in rows])
            pg.commit()
        n_src = len(rows)
        n_dst = pg.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        report.append((t, n_src, n_dst))
        print(f"   {t:<22} SQLite {n_src:>5}  ->  PG {n_dst:>5}"
              + ("" if n_src == n_dst else "   ⚠ ЗӨРҮҮТЭЙ"))

    print("3) id-ийн дарааллыг тааруулж байна ...")
    db.pg_sync_sequences(pg)

    src.close()
    pg.close()
    bad = [r for r in report if r[1] != r[2]]
    print("\nДүн: %d хүснэгт, %d мөр." % (len(report), sum(r[2] for r in report)))
    if bad:
        print("ЗӨРҮҮТЭЙ хүснэгтүүд:", ", ".join(r[0] for r in bad))
        print("(хүлээн авагчид өмнөөс өгөгдөл байсан бол зөрүү гарна — "
              "цэвэр хуулбар хийхийг хүсвэл --truncate-тэй ажиллуулна уу)")
    else:
        print("Бүх хүснэгтийн мөрийн тоо ТААРЧ байна.")


if __name__ == "__main__":
    main()
