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
    plus a polymorphic `contact` table (many phones/faxes/emails per horoo, organization **or**
    member), `salary_request`/`salary_scale`, `member_education`, and the `education_degree` /
    `position` (албан тушаал) / `profession` (мэргэжил) reference tables (each a simple `id`+`name`
    lookup with full CRUD, seeded 16/20/20). A `member` is `last_name`+`first_name` and refers to
    the lookups by id (`position_id`, `profession_id`, `salary_scale_id`); an `organization` refers
    to `school_category` by `school_category_id`. `member_file` holds PDF attachments (батламж) —
    metadata in SQLite, bytes on disk under `uploads/member/`.
- **`admin/`** — the admin site: access control.
  - `users.py` — `permission` → `role` (M:N via `role_permission`) → `app_user`, plus `/api/login`.

## Project layout

```
run.py              # entry point: create_app() + registers both sites' blueprints
db.py               # single source of schema + seed (shared by both sites)
helpers.py          # shared route helpers (rows, require, json_body, error handlers)
client/             # ── CLIENT SITE ──
  admin_units.py    #   blueprint "admin_units": /api/au1|au2|au3, /api/school_category
  union.py          #   blueprint "union": /api/horoo|organization|member|contact|salary*|...
                    #   (holboo — зөвхөн хүснэгт + seed; API маршрут байхгүй)
admin/              # ── ADMIN SITE ──
  users.py          #   blueprint "users": /api/permission|role|user, /api/login
data/
  seed/             # JSON seed data loaded by db.py (admin_unit1|2|3.json)
  sources/          # original .xlsx sources (reference only, not read by code)
docs/               # edu-union-backend.postman_collection.json (manual API reference)
uploads/member/     # uploaded member PDFs (git-ignored; UPLOAD_DIR env overrides)
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
- `python db.py` runs `seed()` (loads `data/seed/admin_unit*.json`), the reference seeds
  (`seed_school_category()`, `seed_salary_scale()`, `seed_education_degree()`, `seed_position()`,
  `seed_profession()`), then `seed_union()` and `seed_users()`. **References must be seeded before
  `seed_union()`** — its sample organization points at `school_category_id`, and the FK pragma
  rejects the insert otherwise. All use `INSERT OR IGNORE` / empty-table guards, so re-running is safe.
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
  (add/rename columns → `_migrate_data()` moves the old values → drop columns) since
  `CREATE TABLE IF NOT EXISTS` won't alter existing tables. When a column is retired, move its data
  in `_migrate_data()` **before** listing it in `_DROP_COLUMNS`.
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
  `OWNER_TYPES`, `CONTACT_TYPES`, `SALARY_STATUSES`, `SALARY_SECTORS`, and the
  `*_FIELDS` allowlists (`ORG_FIELDS`, `MEMBER_FIELDS`, `HOROO_FIELDS`, ...). Add new columns both
  to the relevant `*_FIELDS` and to the schema in `db.py`.
- **File uploads (`/api/member_file`) are the only non-JSON endpoints.** A member can have many
  PDF attachments (батламж). `POST` takes `multipart/form-data` (`member_id`, repeated `file`,
  optional `note`); `_validate_pdf()` rejects anything that isn't a `.pdf` with a `%PDF-` header or
  is over `MAX_FILE_SIZE` (10 MB) — **all files are validated before any is saved**, so a bad file
  in the batch saves nothing. Bytes live on disk at `UPLOAD_DIR` (`uploads/member/<member_id>/<uuid>.pdf`,
  git-ignored, overridable by env var); the DB only stores metadata. `GET .../download` streams the
  PDF back under its original name. `run.py` caps the whole request at `MAX_FILE_SIZE * 5` → 413.
  **On Render the disk is ephemeral** — attach a persistent disk and point `UPLOAD_DIR` at it, or
  uploads vanish on redeploy.
- **`member.member_status` is deliberately free text** (no lookup table, no enum) — `_validate_member()`
  only rejects a non-string / blank value with 400. Don't turn it into a reference table.
- **Registration codes are composed, not typed.** `school_category.id` is the leading **2 digits**
  (`printf('%02d', id)`, so ids are capped at 1–99 and `code` is derived, never stored) →
  `+ organization.org_code` (**3 digits**, hand-entered) = the organization's **5-digit** `full_code`
  → `+ member.union_card_code` (**4 digits**, hand-entered) = `member.union_card_number`, **9 digits**.
  Only the hand-entered parts are writable: `union_card_number` is derived, and a request that sets
  it directly gets a 400. `_digit_code()` enforces the exact digit counts; collisions return 409
  (both on the 5-digit org code and the 9-digit card number). Editing an organization's category or
  `org_code` calls `_recompute_cards()`, which rewrites every member's `union_card_number` in that
  organization — that's why `union_card_code` is stored as its own column.
- **Reference FKs are validated, never free text.** `member.position_id` / `profession_id` /
  `salary_scale_id` and `organization.school_category_id` point at the reference tables;
  `_check_ref()` (client/union.py) turns a bad id into a 400. Reads go through `MEMBER_SELECT` /
  `ORG_SELECT`, which LEFT JOIN the lookups so responses carry `position_name`, `profession_name`,
  `salary_scale_code`, `school_category_name`, etc. alongside the ids.
- **User management** (`admin/users.py`): a `role` has many `permission`s (M:N via `role_permission`);
  an `app_user` picks one `role_id` and inherits all its permissions. Passwords are hashed with
  `generate_password_hash(..., method="pbkdf2")` (scrypt is unavailable in this Python build).
  `public_user()` strips `password_hash` from every response. Seed permissions are the cross-product
  of `PERMISSION_RESOURCES × PERMISSION_ACTIONS` (CRUD per resource) in `db.py`.
- **`contact` is polymorphic**: `owner_type` is `'horoo'`, `'organization'` or `'member'` (the value
  is also the table name), `owner_id` points into the matching table. This is how an owner gets
  **many** phones/faxes/emails — `member` has no single phone column. There is no FK on `contact`;
  ownership is validated in code on insert, and the delete handlers call `_purge_orphan_contacts()`
  to clean up rows whose owner (or cascaded parent) is gone.
- **Unicode**: `app.json.ensure_ascii = False` so Cyrillic is returned unescaped. Preserve this
  when touching JSON serialization config.

## Conventions

- Admin-unit codes are TEXT primary keys (e.g. `"011"`), preserved as strings with leading zeros.
- Union / user ids are INTEGER autoincrement; routes use `<int:...>` converters.
- List endpoints support optional parent-filter query params (`?au1_code=`, `?holboo_id=`,
  `?horoo_id=`, `?organization_id=`, `?owner_type=&owner_id=`, `?resource=`, `?role_id=`, `?status=`).
- Imports are absolute (`from db import get_db`, `from client.union import bp`) and assume the repo
  root is on `sys.path` — always run from the repo root (`python run.py`).
