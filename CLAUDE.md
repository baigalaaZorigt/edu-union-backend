# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Flask + SQLite backend serving two related CRUD domains, both with a built-in HTML
admin UI. Code, comments, error messages, and seed data are in Mongolian (Cyrillic).

1. **Administrative units** (`app.py`) — Mongolia's 3-level geography:
   `admin_unit1` (аймаг/нийслэл) → `admin_unit2` (сум/дүүрэг) → `admin_unit3` (баг/хороо).
2. **Trade union** (`union.py`, registered as a Flask Blueprint) — 4-level hierarchy:
   `holboo` (Холбоо) → `horoo` (Хороо) → `organization` (Гишүүн байгууллага) → `member` (Гишүүн),
   plus a polymorphic `contact` table.

## Commands

No build system or dependency manifest exists. Flask is the only dependency.

```bash
pip install flask              # only dependency

python db.py                   # create schema + seed both domains (idempotent)
python app.py                  # run dev server on http://127.0.0.1:5001 (debug=True)
```

- `app.py` calls `init_db()` on startup, so the schema is always created; it does **not** seed data.
- `python db.py` runs `seed()` (loads `admin_unit*.json`) and `seed_union()` (example union data).
  Both use `INSERT OR IGNORE` / empty-table guards, so re-running is safe.
- No test suite or linter is configured. `emm-backend.postman_collection.json` is the
  reference for exercising the API endpoints manually.

## Architecture notes

- **Two route groups, two files.** `app.py` holds the `/api/au1|au2|au3` routes and registers
  the union Blueprint from `union.py` (`/union`, `/api/holboo|horoo|organization|member|contact`).
  Both register identical `@errorhandler(400/404/409)` handlers that return `{"error": ...}` JSON.
- **`db.py` is the single source of schema.** It defines `SCHEMA` (admin units) and
  `SCHEMA_UNION` (union) separately, both run inside `init_db()`. `get_db()` returns a connection
  with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON` — foreign-key cascades only
  work because of that pragma, set per-connection.
- **Per-request connection lifecycle.** Every handler opens `get_db()`, does its work, and
  `conn.close()`s before returning — including on every error path. When editing handlers, keep
  the close-before-abort pattern; an early `abort()` without closing leaks the connection.
- **Uniqueness/parent checks are manual.** Creates verify the parent row exists (returning 400),
  then rely on a `try/except` around the INSERT to map PK collisions to 409. There are no DB-level
  unique constraints beyond primary keys.
- **`org_stats()` (union.py) computes derived member counts** (total / female / under-35) via SQL
  on every `GET /api/organization`. Under-35 is computed live from `birth_date` using `julianday`.
- **Validated enums** live as module constants in `union.py`: `OWNER_TYPES`, `CONTACT_TYPES`,
  `SCHOOL_TYPES`. `ORG_FIELDS` is the allowlist of organization columns accepted on create/update —
  add new organization columns there and in `SCHEMA_UNION`.
- **`contact` is polymorphic**: `owner_type` is `'horoo'` or `'organization'`, `owner_id` points
  into the matching table. There is no FK on `contact`; ownership is validated in code on insert.
- **Unicode**: `app.json.ensure_ascii = False` so Cyrillic is returned unescaped. Preserve this
  when touching JSON serialization config.

## Conventions

- Admin-unit codes are TEXT primary keys (e.g. `"011"`), preserved as strings with leading zeros.
- Union ids are INTEGER autoincrement; routes use `<int:...>` converters.
- List endpoints support optional parent-filter query params (`?au1_code=`, `?holboo_id=`,
  `?horoo_id=`, `?organization_id=`, `?owner_type=&owner_id=`).
- HTML admin pages are server-rendered Jinja templates in `templates/` (`index.html` for admin
  units at `/`, `union.html` for the union domain at `/union`).
