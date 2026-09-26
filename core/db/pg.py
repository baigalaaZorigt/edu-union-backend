"""Postgres-ийн нимгэн бүрхүүл: SQLite бичиглэлийг гүйцэтгэх агшинд хөрвүүлнэ."""

import re


# ======================= Postgres-ийн нимгэн бүрхүүл =======================
class Row(dict):
    """sqlite3.Row-той ижил аашилдаг мөр: row["ner"] БОЛОН row[0] хоёул ажиллана."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _pg_row_factory(cur):
    cols = [d.name for d in cur.description] if cur.description else []
    def make(values):
        return Row(zip(cols, values))
    return make


_RE_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)", re.IGNORECASE)
_RE_PRINTF = re.compile(r"printf\('%02d',\s*([^)]+)\)")
_RE_JULIAN = re.compile(r"julianday\(([^)]+)\)")


def _to_pg(sql, has_params):
    """SQLite-ийн SQL-ийг Postgres-ийн SQL болгоно (гүйцэтгэх агшинд)."""
    # printf('%02d', x) -> to_char(x, 'FM00')  (2 оронтой тэглэсэн код)
    sql = _RE_PRINTF.sub(r"to_char(\1, 'FM00')", sql)
    # julianday('now') - julianday(x) -> CURRENT_DATE - x::date  (хоногийн зөрүү)
    if "julianday" in sql:
        sql = sql.replace("julianday('now')", "CURRENT_DATE")
        sql = _RE_JULIAN.sub(r"(\1)::date", sql)
    # INSERT OR IGNORE -> ON CONFLICT DO NOTHING
    if "INSERT OR IGNORE" in sql:
        sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO") + " ON CONFLICT DO NOTHING"
    if has_params:
        # psycopg нь параметртэй үед %-г тайлдаг тул эхлээд түүнийг хамгаална,
        # дараа нь ? -> %s болгоно.
        sql = sql.replace("%", "%%").replace("?", "%s")
    return sql


class _PgCursor:
    """sqlite3.Cursor-ийн ашигладаг хэсгийг (fetch*, rowcount, lastrowid) дуурайна."""

    def __init__(self, cur, conn, lastrowid=None):
        self._cur = cur
        self._conn = conn
        self._lastrowid = lastrowid

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    def execute(self, sql, params=()):
        """conn.cursor() маягаар ашиглах үед (seed функцууд) — өөрийгөө буцаана."""
        pg_sql = _to_pg(sql, bool(params))
        m = _RE_INSERT.match(pg_sql)
        want_id = (bool(m) and m.group(1) in self._conn.id_tables()
                   and "RETURNING" not in pg_sql.upper())
        if want_id:
            pg_sql += " RETURNING id"
        try:
            self._cur.execute(pg_sql, tuple(params) or None)
        except Exception:
            self._conn.raw.rollback()
            raise
        if want_id:
            row = self._cur.fetchone()
            self._lastrowid = row["id"] if row else None
        return self

    def executemany(self, sql, seq):
        seq = [tuple(x) for x in seq]
        try:
            self._cur.executemany(_to_pg(sql, True), seq)
        except Exception:
            self._conn.raw.rollback()
            raise
        return self

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        """Сүүлд оруулсан мөрийн id (SQLite-ийн lastrowid-ийн орлуулга).

        `lastval()` ХАРАХГҮЙ: түүнийг хожуу уншихад ЗАВСАРТ хийгдсэн өөр INSERT
        (ж: menu үүсгэхэд _ensure_page() page нэмдэг) -ийн id буцаана. Оронд нь
        INSERT гүйцэтгэх агшинд `RETURNING id`-аар шууд авч хадгалсан утга.
        """
        return self._lastrowid


class _PgConn:
    """sqlite3.Connection-ийн ашигладаг хэсгийг дуурайсан бүрхүүл."""

    def __init__(self, raw):
        self.raw = raw
        self._id_tables = None

    def id_tables(self):
        """`id` баганатай хүснэгтүүд (RETURNING id хийж болох эсэхийг мэдэхэд)."""
        if self._id_tables is None:
            cur = self.raw.cursor()
            cur.execute("SELECT table_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND column_name='id'")
            self._id_tables = {r[0] for r in cur.fetchall()}
        return self._id_tables

    def execute(self, sql, params=()):
        cur = self.raw.cursor(row_factory=_pg_row_factory)
        pg_sql = _to_pg(sql, bool(params))
        m = _RE_INSERT.match(pg_sql)
        want_id = bool(m) and m.group(1) in self.id_tables() and "RETURNING" not in pg_sql.upper()
        if want_id:
            pg_sql += " RETURNING id"
        try:
            cur.execute(pg_sql, tuple(params) or None)
        except Exception:
            self.raw.rollback()      # PG-д алдаа гарвал гүйлгээ хаагддаг
            raise
        new_id = None
        if want_id:
            row = cur.fetchone()     # ON CONFLICT DO NOTHING үед хоосон байж болно
            new_id = row["id"] if row else None
        return _PgCursor(cur, self, new_id)

    def executemany(self, sql, seq):
        seq = [tuple(x) for x in seq]
        cur = self.raw.cursor()
        try:
            cur.executemany(_to_pg(sql, True), seq)
        except Exception:
            self.raw.rollback()
            raise
        return _PgCursor(cur, self)

    def executescript(self, sql):
        cur = self.raw.cursor()
        cur.execute(_to_pg(sql, False))
        self.raw.commit()
        return _PgCursor(cur, self)

    def cursor(self):
        return _PgCursor(self.raw.cursor(row_factory=_pg_row_factory), self, None)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()
