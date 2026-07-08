# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Flask + SQLite **JSON API** (no HTML UI). Code, comments, error messages, and seed data
are in Mongolian (Cyrillic). The backend serves **two sites**, each in its own folder:

- **`client/`** — the client site: business data.
  - `admin_units.py` — Mongolia's 3-level geography:
    `admin_unit1` (аймаг/нийслэл) → `admin_unit2` (сум/дүүрэг) → `admin_unit3` (баг/хороо),
    plus `school_category` reference table.
  - `union.py` — trade-union 4-level hierarchy:
    `holboo` (Холбоо) → `horoo` (Хороо) → `organization` (Гишүүн байгууллага) → `member` (Гишүүн),
    plus a polymorphic `contact` table, `salary_request`/`salary_scale`, `member_education`,
    and the `education_degree` / `position` (албан тушаал) / `profession` (мэргэжил)
    reference tables (each a simple `id`+`name` lookup with full CRUD, seeded 16/20/20).
- **`admin/`** — the admin site: access control.
  - `users.py` — `permission` → `role` (M:N via `role_permission`) → `app_user`, plus `/api/login`.

## Project layout

```
run.py              # entry point: create_app() + registers both sites' blueprints
db.py               # single source of schema + seed (shared by both sites)
helpers.py          # shared route helpers (rows, require, json_body, error handlers)
client/             # ── CLIENT SITE ──
  admin_units.py    #   blueprint "admin_units": /api/au1|au2|au3, /api/school_category
  union.py          #   blueprint "union": /api/holboo|horoo|organization|member|contact|salary*|...
admin/              # ── ADMIN SITE ──
  users.py          #   blueprint "users": /api/permission|role|user, /api/login
data/
  seed/             # JSON seed data loaded by db.py (admin_unit1|2|3.json)
  sources/          # original .xlsx sources (reference only, not read by code)
docs/               # edu-union-backend.postman_collection.json (manual API reference)
admin_units.db      # SQLite database file (at repo root)
```

## Commands

Only dependency is Flask (see `requirements.txt`).

```bash
pip install -r requirements.txt

python db.py                   # create schema + seed everything (idempotent)
python run.py                  # dev server on http://127.0.0.1:5001 (no reload)
FLASK_DEBUG=1 python run.py    # dev server with auto-reload/debugger
gunicorn run:app               # production WSGI server (loads the module-level `app`)
```

- The dev server binds `PORT` (env) or 5001; `debug` is on only when `FLASK_DEBUG=1`.
- On Render/Heroku: build `pip install -r requirements.txt && python db.py`,
  start `gunicorn run:app --bind 0.0.0.0:$PORT` (see `render.yaml`).

- `run.py`'s `create_app()` calls `ensure_seeded()` on startup: it always creates the schema,
  **auto-seeds any empty table** (idempotent), and **always re-runs `seed_users()`** so newly added
  `PERMISSION_RESOURCES` and the admin's grants stay complete (needed for auth to work). This is what
  populates data on Render/Heroku, where `python db.py` is not run separately. Run `python db.py`
  (`seed_all()`) locally to force a full re-seed.
- `python db.py` runs `seed()` (loads `data/seed/admin_unit*.json`), `seed_union()`,
  `seed_school_category()`, `seed_salary_scale()`, `seed_education_degree()`, and `seed_users()`.
  All use `INSERT OR IGNORE` / empty-table guards, so re-running is safe.
- `seed_users()` creates the first admin account **only when `app_user` is empty**: `admin` / `admin123`.
- No test suite or linter is configured. `docs/edu-union-backend.postman_collection.json` is the
  reference for exercising the API endpoints manually.

## Architecture notes

- **Two sites, one Flask app.** `run.py` builds the app via `create_app()` and registers three
  blueprints — `admin_units` + `union` (client site) and `users` (admin site). Blueprints are
  plain route modules; they do **not** register their own error handlers.
- **Auth is enforced globally in `auth.py`.** `run.py` registers `app.before_request(require_auth)`,
  so **every request except `/api/login` requires a Bearer token** (`Authorization: Bearer <jwt>`)
  → else 401. Tokens are stateless **JWTs** (PyJWT, HS256) with `sub`/`iat`/`exp` claims, signed with
  `SECRET_KEY` (env; set it in production), valid 12h. `/api/login` returns the token. **Authorization is derived, not hand-wired**:
  `require_auth()` maps the URL's first path segment → resource (au1/au2/au3 → `admin_unit`) and the
  HTTP method → action (GET→read, POST→create, PUT/PATCH→update, DELETE→delete), then requires the
  `resource.action` permission on the user's role → else 403. So **adding a new `/api/<resource>`
  route automatically needs `<resource>.{action}` permissions** — add the resource to
  `PERMISSION_RESOURCES` in `db.py` (which is the cross-product source for the seeded CRUD permissions).
- **Error handling is centralized.** `register_error_handlers(app)` in `run.py` maps
  400/401/403/404/409 to `{"error": ...}` JSON for the whole app — including unmatched-URL 404s and
  aborts raised inside any blueprint (Flask falls back to app-level handlers for blueprint errors).
- **Shared helpers live in `helpers.py`.** `rows()` (Row→dict list), `require(data, fields)`
  (required-field check → 400), `json_body()` (parse JSON body or 400), and
  `register_error_handlers(target)`. All three route modules import these — do not re-define them.
- **`db.py` is the single source of schema.** It defines `SCHEMA` (admin units), `SCHEMA_UNION`,
  `SCHEMA_REF`, and `SCHEMA_USER` separately, all run inside `init_db()`. `get_db()` returns a
  connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON` — foreign-key cascades
  only work because of that pragma, set per-connection. `_migrate()` patches older DBs in place
  (add/rename/drop columns) since `CREATE TABLE IF NOT EXISTS` won't alter existing tables.
- **Per-request connection lifecycle.** Every handler opens `get_db()`, does its work, and
  `conn.close()`s before returning — including on every error path. When editing handlers, keep
  the close-before-abort pattern; an early `abort()` without closing leaks the connection.
- **Uniqueness/parent checks are manual.** Creates verify the parent row exists (returning 400),
  then rely on a `try/except` around the INSERT to map PK/UNIQUE collisions to 409. There are no
  DB-level unique constraints beyond primary keys and a few `UNIQUE` columns (`permission.code`,
  `role.name`, `app_user.username`, `salary_scale.code`).
- **`org_stats()` (client/union.py) computes derived member counts** (total / female / under-35)
  via SQL on every `GET /api/organization`. Under-35 is computed live from `birth_date` using `julianday`.
- **Validated enums / field allowlists** live as module constants in `client/union.py`:
  `OWNER_TYPES`, `CONTACT_TYPES`, `SCHOOL_TYPES`, `SALARY_STATUSES`, `SALARY_SECTORS`, and the
  `*_FIELDS` allowlists (`ORG_FIELDS`, `MEMBER_FIELDS`, ...). Add new columns both to the relevant
  `*_FIELDS` and to the schema in `db.py`.
- **User management** (`admin/users.py`): a `role` has many `permission`s (M:N via `role_permission`);
  an `app_user` picks one `role_id` and inherits all its permissions. Passwords are hashed with
  `generate_password_hash(..., method="pbkdf2")` (scrypt is unavailable in this Python build).
  `public_user()` strips `password_hash` from every response. Seed permissions are the cross-product
  of `PERMISSION_RESOURCES × PERMISSION_ACTIONS` (CRUD per resource) in `db.py`.
- **`contact` is polymorphic**: `owner_type` is `'horoo'` or `'organization'`, `owner_id` points
  into the matching table. There is no FK on `contact`; ownership is validated in code on insert.
- **Unicode**: `app.json.ensure_ascii = False` so Cyrillic is returned unescaped. Preserve this
  when touching JSON serialization config.

## Conventions

- Admin-unit codes are TEXT primary keys (e.g. `"011"`), preserved as strings with leading zeros.
- Union / user ids are INTEGER autoincrement; routes use `<int:...>` converters.
- List endpoints support optional parent-filter query params (`?au1_code=`, `?holboo_id=`,
  `?horoo_id=`, `?organization_id=`, `?owner_type=&owner_id=`, `?resource=`, `?role_id=`, `?status=`).
- Imports are absolute (`from db import get_db`, `from client.union import bp`) and assume the repo
  root is on `sys.path` — always run from the repo root (`python run.py`).
