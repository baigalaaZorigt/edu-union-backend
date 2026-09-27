# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Flask + SQLite **JSON API** (no HTML UI). Code, comments, error messages, and seed data
are in Mongolian (Cyrillic). The backend serves **two sites**, split by **who calls them**:
`admin/` is everything the admin panel calls (token + permission), `client/` is only the
portal's token-free API (`/api/portal/...`, `/api/public/...`). What both sides share lives in
`core/`.

- **`admin/`** — the admin site (every route needs a token, see `core/auth.py`).
  - `admin_units.py` — Mongolia's 3-level geography:
    `admin_unit1` (аймаг/нийслэл) → `admin_unit2` (сум/дүүрэг) → `admin_unit3` (баг/хороо),
    plus `school_category` reference table.
  - `union/` — trade-union data, one blueprint (`union`) split into one module per resource
    (`__init__.py` creates `bp` and imports the route modules; `common.py` holds what several
    of them share — `UPLOAD_DIR`, `ORG_FULL_CODE_SQL`, `_check_ref`, `_digit_code`,
    `_purge_orphan_contacts`, …; a constant used by only one module lives in that module):
    `holboo` (Холбоо) → `horoo` (Хороо, `horoo.py`), and separately `organization`
    (Гишүүн байгууллага, `organization.py`) → `member` (Гишүүн, `member.py`).
    **An `organization` does not belong to a `horoo`** — `horoo_id` was removed, so
    organizations are registered standalone and are no longer cascade-deleted with a horoo,
    plus a polymorphic `contact` table (`contact.py`; many phones/faxes/emails per horoo,
    organization **or** member), `salary_request`/`salary_scale` (`salary.py`),
    `member_education.py`, `member_reward.py` (шагнал, урамшуулал — many per member), and the
    `education_degree` (`id`+`name`) / `position` (албан тушаал) / `profession` (мэргэжил) /
    `reward_type` (шагналын төрөл) / `structure` (бүтцийн удирдлага) reference tables
    (`references.py`; the last four are `id`+`code`+`name`; each has full CRUD, seeded
    16/20/20/12/22). A `member` is `last_name`+`first_name` and refers to the lookups by id
    (`position_id`, `profession_id`, `salary_scale_id`); an `organization` refers to
    `school_category` by `school_category_id`. `member_file.py` holds PDF attachments
    (батламж) — metadata in SQLite, bytes on disk under `uploads/member/`.
  - `users/` — `permission` → `role` (M:N via `role_permission`) → `app_user`, plus `/api/login`
    and `user_scope` (Хамрах хүрээ — which *data* a user may see, 1:1 with `app_user`), plus the
    **self-service** routes a Зөвлөх мэргэжилтэн needs on first login: `/api/change_password`,
    `/api/me`, `/api/me/scope`, `/api/me/organizations`, `/api/me/onboarding/complete`
    (`specialist_onboarding_api_spec.md`). `GET /api/me/specialist` (`specialist.py`) is the
    manager's side: from the caller's scope (`organization_id`, else the first
    `organization_ids`) it returns the active Зөвлөх мэргэжилтэн covering that school — first
    a `rural` specialist listing the school in `organization_ids` (ХОН is an explicit
    assignment, not a category), else one whose `school_type` is the school's category
    (`SCHOOL_TYPE_CATEGORY` reversed) and whose `district_au2_code` equals the school's
    `au2_code`; lowest id wins. 403 without a school in scope (admin, specialists), 404 when
    nobody covers it. Returns name/email/structure only (+ `matched_by`). `/api/login` is guarded by `login_guard.py`: failed
    attempts go to the `login_attempt` table (shared by all workers); 5 per (username + IP) or 20
    per IP within 15 min → 429, so nobody can lock `admin` out from another IP. IP = `X-Real-IP`
    (`core.helpers.client_ip()`). Passwords hash with `pbkdf2:sha256:600000` (OWASP; werkzeug's
    1M default cost ~0.7 s CPU per login on t3.micro) and older hashes are upgraded on login.
  - `content/` — the portal's dynamic menu & content: `menu` (Цэс, 2 levels deep, typed) →
    `page` (Контент хуудас, one per `type='page'` menu) → `page_block` (ordered content blocks:
    text / image / video / file / link), plus `/api/upload` for images and documents.
  - `forms/` — the admin half of the survey / poll engine (`/api/admin/...`).
  - `news.py` — the admin half of Мэдээ, зар (`/api/admin/news...`): the card list plus
    its `news_block` content blocks.
  - `feedback.py` — the admin half of Санал хүсэлт / Өргөдөл гомдол
    (`GET|DELETE /api/admin/suggestions|complaints`).
  - `notifications/` — Мэдэгдэл: the admin send side (`/api/admin/notifications`) **and**
    every user's own 🔔 inbox (`/api/notifications`), which needs no permission.
  - `dashboard.py` — `GET /api/admin/dashboard/summary`: the one aggregate call behind the
    dashboard's cards, bar chart and gender donut.
  - `settings.py` — `portal_settings`, the portal's **singleton** settings row
    (header, hero banner, contacts, map) — `GET|PUT|PATCH /api/portal_settings`.
  - `legal.py` — Хууль тогтоомж: `legal_document` (+ `legal_document_block`) CRUD, block
    reorder (`/api/legal_document...`, `/api/legal_document_block/<id>`).
  - `home.py` — the portal home page's `banner` (slider) and `partner` (Хамтрагч байгууллага)
    lists: `GET|POST /api/banner`, `GET|PUT|PATCH|DELETE /api/banner/<id>`, same for `/api/partner`.
- **`client/`** — the portal site, **token-free** (`PUBLIC_PREFIXES` in `core/auth.py`):
  `forms.py` (list, open, submit surveys), `news.py` (read news), `feedback.py` (send
  suggestions/complaints), `settings.py` (`/api/public/portal_settings` and
  `/api/portal/portal_settings`, read-only), `home.py` (`/api/portal/banners`,
  `/api/portal/partners` → `{items: [...]}` (partner: id, name, url, icon, logo_url),
  `Cache-Control: public, max-age=300`),
  `legal.py` (`/api/portal/legal_documents[/<id>]` — visible rows; detail adds `blocks`),
  `content.py` (`/api/portal/menu`, `/api/portal/page/<menu_id>`, `/api/portal/page_block`,
  `POST /api/portal/upload` — the admin reads' exact responses, built by the same
  `core/content_core.py` functions, but only visible menus (the whole parent chain
  `is_visible`) and `published` pages on visible menus; hidden/draft → 404 or `[]`. The
  token-free upload has the admin upload's type/size rules plus a per-IP limit of 10 per 10 min
  per worker → 429),
  `stats.py` (`/api/portal/membership_structure` — «Гишүүнчлэлийн бүтэц» pie: members per
  school category, plus `rural` = members of schools a ХОН specialist is assigned (taken out of
  their category, never double-counted) and `other` = schools without a category; integer
  percents that sum to exactly 100 (largest remainder); only aggregates, 5-min cache).
- **`core/`** — shared by both sites: `db.py`, `auth.py`, `helpers.py` and the domain cores
  below. **`client/` never imports from `admin/`**; anything both need goes into `core/`.

Мэдээ (news) spans both sites the same way as the survey engine: `core/news_core.py` (validation,
`public_*` shaping) is imported by `admin/news.py` (`/api/admin/news...` — build, block, publish)
and `client/news.py` (`/api/portal/news...` — list and read, token-free). See
`news_api_spec.md`; the portal settings live in `portal_settings_api_spec.md` and share
`core/settings_core.py` (`SETTINGS_FIELDS`, `get_row()`, `public()`) between `admin/settings.py`
and `client/settings.py`.

Хамрах хүрээ (`user_scope`) does the same across both sites: `core/scope_core.py` turns one
user's scope into the SQL that `admin/union/` adds to `GET /api/member` /
`GET /api/organization` and that `admin/users/` uses for `/api/me/organizations`. See
`specialist_onboarding_api_spec.md` and `user_scope_api_spec.md`.

Санал хүсэлт / Өргөдөл гомдол follows the same split at a much smaller scale:
`core/feedback_core.py` (validation, pagination, `public_row`) is imported by
`client/feedback.py` (`POST /api/portal/suggestions|complaints` — token-free) and
`admin/feedback.py` (`GET|DELETE /api/admin/suggestions|complaints`). See
`feedback_api_spec.md`.

The survey / poll engine spans both sites and shares one domain core:
`core/forms_core/` (validation, `public_*` shaping, result aggregation) is imported by
`admin/forms/` (`/api/admin/...` — build forms, questions, options, PDFs, read results)
and `client/forms.py` (`/api/portal/...` — list, open, submit). See
`survey_poll_backend_spec_v1.md` for the spec it implements.

## Project layout

**Rule: no `.py` file over 300 lines.** A module that outgrows it becomes a package with the
same import path: `__init__.py` creates the blueprint (`bp`) and imports the route submodules
*after* it, each submodule does `from <package> import bp`, and every name other code imports
is re-exported from `__init__.py` — so `from admin.content import remove_upload`,
`from core.orm.models import Member`, `from core.forms_core import ...` keep working. Blueprint and
function names never change on a split, so endpoint names stay the same.

```
run.py              # entry point: create_app() + registers both sites' blueprints
core/               # ── SHARED (хоёр site хуваалцана) ──
  orm/              #   SQLAlchemy 2.0 — engine/session (__init__), Base + Int/Str (base.py),
    models/         #     44 model (geo, union, union_refs, users, content, news, forms)
    query.py        #     paginate(), get_or_404()
    soft.py         #     SoftSession — бүх устгал soft delete (deleted_at), уншилтын шүүлт
  db/               #   DB_PATH/DATABASE_URL + seeds (ORM) + FROZEN baseline schema code
    schema_*.py schema.py pg*.py migrate*.py    # хуучин DDL/migration — зөвхөн alembic 0001 ба
                                                # Alembic-ээс өмнөх DB-г шинэчлэхэд (засахгүй)
    seed_ref|seed_data|seed_portal.py, reference_data.py
    bootstrap.py    #     migrate() (Alembic), seed_all(), ensure_seeded()
    __main__.py     #     python -m core.db
alembic/            # migration-ууд: 0001_baseline (хуучин бүх схем), 0002_legal_document,
                    #   0003_partner_logo, 0004_soft_delete (бүх хүснэгтэд deleted_at)
  auth.py           #   JWT + global permission check (before_request)
  helpers.py        #   require, json_body, pick, client_ip, now_str, page_params, list_json
  forms_core/       #   survey/poll домэйний цөм (base, questions, results, documents)
  news_core.py  scope_core.py  feedback_core.py  settings_core.py  home_core.py  legal_core.py
  content_core.py   #   цэс/хуудас/блокийн хариу хэлбэр (admin ба портал хуваалцана)
  content_storage.py #  контент файл: UPLOAD_DIR, STORE, validate/save_upload, remove_upload
  search_core.py    #   порталын хайлтын индекс, тааруулалт, snippet
  xlsx.py           #   Excel экспорт (xlsxwriter constant_memory, bold+freeze толгой)
  storage.py        #   файлын сан: S3 (S3_BUCKET) эсвэл локал диск — Area(area, local_dir)
  audit.py          #   хүсэлт бүрийн JSON лог -> stdout -> (awslogs) CloudWatch
admin/              # ── ADMIN SITE (токен + эрх) ──
  admin_units.py    #   "admin_units": /api/au1|au2|au3, /api/school_category
  union/            #   "union": horoo, organization, member, contact, salary, references,
                    #   member_education, member_reward, member_file (+ common)
                    #   (holboo — зөвхөн хүснэгт + seed; API маршрут байхгүй)
  users/            #   "users": permissions, roles, accounts, scope, me (login/me/...) + common
  content/          #   "content": menu, page, blocks, upload (+ core/content_core, content_storage)
  forms/            #   "admin_forms": forms, questions, options, documents, results
  notifications/    #   "notifications": admin_routes (/api/admin/notifications), inbox
                    #   (/api/notifications), common (validation, fan-out, dispatch_due)
  news.py           #   "admin_news": /api/admin/news|news_blocks (мэдээ, зар)
  feedback.py       #   "admin_feedback": /api/admin/suggestions|complaints
  dashboard.py      #   "admin_dashboard": /api/admin/dashboard/summary
  settings.py       #   "portal_settings": /api/portal_settings (GET/PUT/PATCH)
  home.py           #   "home_content": /api/banner, /api/partner (нүүр хуудас)
  legal.py          #   "legal": /api/legal_document(_block) (хууль тогтоомж)
client/             # ── CLIENT SITE (портал, токенгүй) ──
  forms.py          #   "portal_forms": /api/portal/forms...
  news.py           #   "portal_news": /api/portal/news...
  feedback.py       #   "portal_feedback": /api/portal/suggestions|complaints
  settings.py       #   "public_settings": /api/public|portal/portal_settings
  home.py           #   "portal_home": /api/portal/banners|partners
  search.py         #   "portal_search": /api/portal/search, /api/portal/search/suggest
  stats.py          #   "portal_stats": /api/portal/membership_structure
  content.py        #   "portal_content": /api/portal/menu|page|page_block|upload
  legal.py          #   "portal_legal": /api/portal/legal_documents
scripts/
  migrate_to_pg.py  # SQLite -> Postgres хуулах
  migrate_uploads_to_s3.py  # хуучин локал файлуудыг S3 руу (нэг удаа, идемпотент)
  send_due_notifications.py  # cron: хуваарьт мэдэгдлийг илгээх (dispatch_due)
tests/              # pytest: conftest.py (түр DB + fixtures), test_<area>_<topic>.py,
                    #   _<area>_helpers.py (олон файлд хуваалцсан fixture/туслах)
data/
  seed/             # JSON seed data loaded by core/db (admin_unit1|2|3.json)
  sources/          # original .xlsx sources (reference only, not read by code)
docs/               # edu-union-backend.postman_collection.json (manual API reference)
uploads/member/     # uploaded member PDFs (git-ignored; UPLOAD_DIR env overrides)
uploads/content/    # portal images/documents (git-ignored; CONTENT_UPLOAD_DIR env overrides)
uploads/form/       # poll PDFs (git-ignored; FORM_UPLOAD_DIR env overrides)
admin_units.db      # SQLite database file (at repo root)
```

## Commands

Flask + PyJWT + gunicorn, and `psycopg[binary]` **only** when running on Postgres
(see `requirements.txt`).

```bash
pip install -r requirements.txt

python -m core.db              # migrate (Alembic) + seed everything (idempotent)
alembic revision -m "..."      # шинэ схемийн migration (autogenerate бол ЗААВАЛ Postgres-тэй)
python run.py                  # dev server on http://127.0.0.1:5001 (no reload)
FLASK_DEBUG=1 python run.py    # dev server with auto-reload/debugger
gunicorn run:app               # production WSGI server (loads the module-level `app`)

pip install -r requirements-dev.txt   # pytest, moto, openpyxl, ruff
python -m pytest tests -q      # the whole pytest suite (~620 tests, ~20 s)
bash scripts/check.sh          # ruff + structural rules + pytest (--fast: no pytest)
bash scripts/check.sh --pg     # + Postgres in docker: alembic, model drift, Postman ×2
```

- **`scripts/check.sh` is the quality gate** and the `/quality` Claude Code skill
  (`.claude/skills/quality/SKILL.md` — standards, lint, refactor, review, test) drives it. Lint is
  `ruff.toml` (`E9`, `F`, `B`; style rules deliberately off). The structural checks enforce the
  rules below mechanically: every `.py` ≤ 300 lines, no SQL text outside `core/db/` + models,
  `client/`/`core/` never import `admin/`, every blueprint registered in `run.py`, every
  `select(*Model.__table__.c)` has `.select_from(Model)` (soft-delete filter). CI still runs only
  pytest.
- The dev server binds `PORT` (env) or 5001; `debug` is on only when `FLASK_DEBUG=1`.
- **CI/CD: every push to `main` tests and deploys itself** (`.github/workflows/deploy.yml`).
  Job `test` runs pytest on Python 3.12 (the container's version); only if it passes, job
  `deploy` SSHes to the EC2 box (port 22 is open to all IPs; key-only auth) with the repo
  secrets `EC2_SSH_KEY` (the `edu-union-key.pem` contents) and `EC2_KNOWN_HOSTS` (pinned host
  key, `StrictHostKeyChecking=yes`). On the box it `git fetch` + `reset --hard origin/main` +
  `clean -fd`, then runs `deploy/remote-deploy.sh`: tag the running image `:previous` → build →
  `ensure_seeded()` in a throwaway container → `compose up -d` → wait for `healthy`; any failure
  rolls back to `:previous` and the old commit. The job ends with an HTTPS check (portal 200,
  protected 401).
  Manual re-run: Actions → test-and-deploy → Run workflow.
- On AWS: `bash deploy/provision.sh` creates everything (RDS + EC2 + security groups +
  SSH key, idempotent); `DATABASE_URL=... python scripts/migrate_to_pg.py` copies SQLite → Postgres.
  Live at **https://api.fmesu.mn** (EC2 `i-03648c2bcc4e19350`, 13.196.178.202 → nginx → docker →
  RDS `edu-union-db`). The RDS instance is **not** publicly accessible: reach it through the app
  server (`ssh -i edu-union-key.pem -L 5432:<rds-endpoint>:5432 ec2-user@13.196.178.202`).

- `run.py`'s `create_app()` calls `ensure_seeded()` on startup: it always creates the schema,
  **auto-seeds any empty table** (idempotent), and **always re-runs `seed_users()`** so newly added
  `PERMISSION_RESOURCES` and the admin's grants stay complete (needed for auth to work). This is what
  populates data in the container, where `python -m core.db` is not run separately. Run `python -m core.db`
  (`seed_all()`) locally to force a full re-seed.
- `python -m core.db` runs `seed()` (loads `data/seed/admin_unit*.json`), the reference seeds
  (`seed_school_category()`, `seed_salary_scale()`, `seed_education_degree()`, `seed_position()`,
  `seed_profession()`, `seed_reward_type()`), then `seed_union()`, `seed_menu()` (the portal's default menu tree),
  `seed_portal_settings()` (the singleton settings row, from `DEFAULT_PORTAL_SETTINGS`) and
  `seed_users()`. **References must be seeded before
  `seed_union()`** — its sample organization points at `school_category_id`, and the FK pragma
  rejects the insert otherwise. All use `INSERT OR IGNORE` / empty-table guards, so re-running is safe.
- `seed_users()` creates the first admin account **only when `app_user` is empty**: `admin` / `admin123`.
- **Tests: `python -m pytest tests -q`.** `tests/conftest.py` points `core.db.DB_PATH` and the
  three upload dirs at a temp folder **before** importing `run`, so the suite never touches
  `admin_units.db` or `uploads/`; fixtures `api` (admin token), `anon` (no token) and
  `make_user(perms)` (a fresh role + user + token). Each test makes its own rows. A test that
  documents a known bug is `xfail(strict=True)` — fixing the bug means removing the mark.
  The Postman collection (`docs/edu-union-backend.postman_collection.json`) is the second,
  black-box suite, run against a live server. It runs **top to bottom** (Postman Runner or
  `newman run docs/edu-union-backend.postman_collection.json --env-var base_url=...`, **from the
  repo root** — the form-data requests upload `docs/fixtures/sample.png|pdf` by relative path): 664 requests,
  ~1273 assertions (a few are conditional), and repeatable — three consecutive runs leave every table's **visible**
  row count (`deleted_at IS NULL`) unchanged; since every delete is soft, hidden rows do pile up. Every request is green, on a fresh database too (`Нэгийг авах` in
  the member_education folder reads the row its own `Нэмэх` created, not a seed id). **Keep it that way when adding requests:** run "0. Нэвтрэлт" first (it stores
  `{{token}}`), have each folder's `Нэмэх` save the new id into a `{{new_*}}` variable, and point
  that folder's `Засах`/`Устгах` at `{{new_*}}` only — never at a seeded row. Every `Засах` is
  followed by a `— PATCH-аар мөн` twin (same body, status-only assertion) so that **every route,
  both verbs, is exercised**; if you add a `PUT` route, add its `PATCH` twin too. The
  `ҮЭ — Алдааны шалгалт (сөрөг тест)` is the union-side negative folder: it creates one
  organization, drives every 400/405/401 path through it (bad category, bad `org_code`, wrong
  method, no token) and deletes it again. The `Мэдээ 1..6` folders cover news + portal settings
  the same way — one news item is built, blocked, reordered, published, read back through the
  token-free portal, then deleted; `Мэдээ 4` overwrites the settings singleton and **restores its
  seeded values** in the same folder, so the row is left as it was found. The
  `Судалгаа 1..8` folders additionally show the pattern for **public** endpoints: every
  `/api/portal/` request carries `"auth": {"type": "noauth"}` so the run proves a guest can
  submit without a token, and the cleanup folder deletes forms with `?hard=1` (a form with
  answers is otherwise only archived — its questions and answers stay readable). `GET`s may read seed
  rows (`{{au1_code}}`=011 etc.). The `Санал хүсэлт 1` folder sends both feedback forms
  token-free, walks the validation rejections, then reads them back through the admin list
  (search / paging / `per_page` cap) and deletes all four rows it made. The
  `Нүүр 1..2` folders (banner / partner) each create one row, read it back through the
  token-free portal (and check it disappears once hidden or expired), walk the 400/401 paths and
  delete it again; the role folder's `Код давхцвал → 409` proves `role.code` uniqueness. The
  `Мэдэгдэл 1` folder sends a notification to a **role-less** user (proving the inbox needs no
  permission while `/api/admin/notifications` still answers 403 to them) and cleans its `sent`
  row up with `?hard=1`, since a plain `DELETE` on a sent notification is a 422 by design.
  `Портал 8` checks the uploaded image is **still served** (200) after its block is deleted.
  The `Soft delete 1` folder proves the soft-delete contract end to end: a deleted user is 404 on
  read and on a second delete and gone from the list, the same `username` can be created again;
  deleting an organization that still has a member is a 409 naming that member, deleting the
  member hides its contacts, then the organization goes and its `org_code` is free again; a
  deleted banner's uploaded image is still served token-free (200). The `Холбоос 1` folder walks
  every `RESTRICT` relation at once: it builds one of each lookup + a school category (id 97) +
  aimag 981 / sum 98101 + a role, an organization and a member / user that use them, proves each
  delete is a 409 naming the right table (and changes nothing), then unlinks (deletes the member
  and the user) and deletes everything with 200. The
  `Мэргэжилтэн 1` folder covers the specialist flow
  end to end: it builds its own role + two organizations (one in scope, one out) + user, logs
  in with the initial password, changes it, fills the scope through `/api/me/scope`, then
  proves `GET /api/member` / `GET /api/organization` come back **filtered** and that the
  out-of-scope organization answers 403 — all under `{{spec_token}}`, not `{{token}}`.
  **Postman runs every test script in one sandbox**, so declare script locals with `var`
  (a second `const data` anywhere in the collection is a `SyntaxError`, not a failed test).
  A folder that creates N rows must delete all N. Pointing a `PUT`
  at `/api/role/1` or a `DELETE` at `/api/user/1` wipes the admin's grants or the admin account
  itself and every later request 403s.

## Architecture notes

- **All queries go through the SQLAlchemy 2.0 ORM — no SQL strings in app code.** `core.orm`:
  one engine per process (`DATABASE_URL` set → Postgres via `postgresql+psycopg`, else SQLite at
  `core.db.DB_PATH`, read when the engine is built so tests can repoint it); Postgres gets a
  `QueuePool` (`DB_POOL_MAX`, default 5, `pool_pre_ping`), SQLite gets `PRAGMA foreign_keys=ON` on
  every connection (cascades depend on it). `session()` is **one session per request** (Flask
  `g`), rolled back and closed by `teardown_appcontext` — so an `abort()` anywhere leaks nothing and
  uncommitted writes never survive an error; handlers call `session().commit()` and map
  `IntegrityError` to 409 after `rollback()`. Outside a request use `new_session()` and close it.
  `create_app()` calls `orm.dispose()` after `ensure_seeded()` so the gunicorn `--preload` master
  hands no sockets to its forks. Models (`core/orm/models/`) mirror the production schema exactly
  (Alembic `compare_metadata` against Postgres = 0 differences); their `Int`/`Str` column types
  **coerce bound values** — `"5"` → `5`, a non-numeric string → `NULL`, a number into TEXT → str —
  because query strings and JSON send ids as strings, which SQLite tolerates and Postgres rejects
  (`integer = varchar`). Anything dialect-specific (`printf`, `julianday`, `DATE()`) is computed
  in Python instead (`full_code`, the under-35 cutoff, trend days). `Base.to_dict()` = the old
  `dict(row)`; joined/derived columns come from labelled selects read with `.mappings()`.
- **Deleting a referenced row is a 409 that says what refers to it** (`core/orm/restrict.py`).
  `RESTRICT` lists the *reference* relations — a child that would lose its value: school category,
  structure, position, profession, salary scale, education degree, reward type ← the rows that
  picked them; role ← users; organization ← members and a manager's `user_scope.organization_id`;
  admin units ← organizations / members / `user_scope.district_au2_code` (logical `au*_code`
  links with no FK). `check_references()` runs inside `soft_delete()`, so every handler gets it
  with no code of its own, and answers `409 {"error": "«X» (албан тушаал) устгах боломжгүй:
  үүнтэй холбоотой 3 гишүүн (…) бүртгэлтэй байна. Эхлээд тэдгээрийн холбоосыг салгаж …",
  "references": [{table, label, count, examples}]}` (`Referenced` is a `Conflict` with `extra`,
  which `register_error_handlers` merges into the JSON). Hidden (soft-deleted) children do not
  count. `count` is always the full number, but `examples` (names) are filtered by the caller's
  `user_scope` (`_scope_filter()`): a scoped user sees only names they could read anyway, and no
  names at all for users/admin units — the 409 must not leak members outside their scope. **Ownership cascades are untouched** — news → blocks, form → questions, member →
  education/rewards/files/contacts, menu → sub-menus/page, role → `role_permission`, and the
  admin-unit hierarchy (aimag → sum → bag) still go with their parent; but every row a cascade
  would hide is checked too, so an aimag whose sum has an organization is a 409 naming the sum.
  Not covered: audit columns (`created_by`/`updated_by`), `notifications.role_id` history, and the
  ХОН `user_scope.organization_ids` JSON list.
- **Every delete is a soft delete — every table, and nothing is ever restored**
  (`core/orm/soft.py`, Alembic 0004 added `deleted_at TEXT` to all 46 tables). `new_session()` /
  `session()` hand out a `SoftSession`, so handlers keep writing plain `s.delete(obj)` /
  `s.execute(delete(Model)...)`, and the session turns that into `deleted_at = now_str()`:
  **reads** — every ORM `SELECT`/`UPDATE`/`DELETE` gets `deleted_at IS NULL` through
  `with_loader_criteria` (JOIN `ON` clauses and subqueries too), plus `_filter_core_froms()` for
  a statement whose main `FROM` is a bare `Table` (`select(*Model.__table__.c)`). That fallback
  does not reach subqueries (e.g. `paginate()`'s `COUNT`), so **a new select over `__table__.c`
  must add `.select_from(Model)`** — see `MEMBER_QUERY` / `ORG_QUERY`. **Deletes** — the FK
  rules are replayed from model metadata (`ON DELETE CASCADE` → the children are soft-deleted
  too; `SET NULL` is deliberately **not** replayed — the parent row stays in the table, so e.g.
  `news.created_by` keeps pointing at a deleted user) plus the polymorphic `contact` rows of a
  horoo/organization/member, all with one timestamp. Single-column UNIQUE text values
  (`username`, `role.name`, `permission.code`, `menu.slug`, `salary_scale.code`,
  `member_file.stored_name`) get `~deleted~<id>` appended so the name is free to reuse; a new row
  whose PK/other UNIQUE key (admin-unit code, `role_permission`, `user_scope`, `page.menu_id`)
  collides with a *hidden* row replaces it physically (`before_flush`). **Files stay**: a delete
  no longer calls `remove_upload()` / deletes member PDFs (the user chose "зөвхөн нуух" —
  hide only, no restore endpoint, no hard delete); only *replacing* a file on update still removes
  the old one. `?hard=1` (forms, notifications) survives as a flag with its old business meaning
  but is soft too. Raw SQL (`text()`, `engine().connect()`) sees hidden rows; so do the seeds,
  which open `new_session(include_deleted=True)` so a deleted seed row is neither re-created nor a
  PK collision — and `seed_users()` un-hides the admin role's `role_permission` links so admin
  always keeps every permission. `tests/test_soft_delete.py` covers it.
- **Schema changes go through Alembic.** `alembic/versions/0001_baseline.py` runs the frozen
  legacy DDL (`core/db/schema*.py` + `_pg_schema()` + timestamp triggers), so a fresh database is
  byte-for-byte the production schema (checked with `pg_dump`). `core.db.bootstrap.migrate()`
  (called by `ensure_seeded()` on every start): a database from before Alembic (tables but no
  `alembic_version` — production, the committed `admin_units.db`) is brought up to date by the old
  `init_db()` once and then **stamped** `0001` (no data touched); after that it is always
  `alembic upgrade head`. New columns/tables = a new revision after 0001 — never edit the
  `SCHEMA_*` strings or `_MIGRATIONS` again. Run `--autogenerate` against **Postgres** (SQLite's
  reflection reports false PK/UNIQUE differences) and review it. `core.db.get_db()` is the only
  raw connection left and exists solely for that frozen code and `scripts/migrate_to_pg.py`.
- **Two sites, one Flask app.** `run.py` builds the app via `create_app()` and registers fourteen
  blueprints — `admin_units` + `union` + `users` + `content` + `admin_forms` + `admin_news` +
  `portal_settings` + `admin_feedback` + `notifications` + `admin_dashboard` (admin site) and
  `portal_forms` + `portal_news` + `portal_feedback` + `public_settings` (client site). Blueprints are plain route modules; they do **not** register their
  own error handlers. **A new blueprint is invisible until it is registered here** — that is the
  one step `CREATE TABLE`/route decorators cannot do for you.
- **CORS is hand-rolled in `run.py`** (`add_cors_headers` via `app.after_request`) — no extra
  dependency. `CORS_ORIGINS` (env, comma-separated) defaults to `*`; that is safe here because
  auth is a Bearer token, never a cookie, so a wildcard grants no CSRF. `require_auth()` already
  short-circuits `OPTIONS`, so preflights pass. **Production does not use the default**: the
  deployed server sets `CORS_ORIGINS=https://fmesu.mn,https://www.fmesu.mn` (in
  `/opt/edu-union/.env`, and `deploy/provision.sh` bakes the same value into new instances). An
  origin outside the list simply gets no `Access-Control-Allow-Origin` header back — the response
  itself is unchanged, since the browser is what enforces this.
- **Auth is enforced globally in `core/auth.py`.** `run.py` registers `app.before_request(require_auth)`,
  so **every request except `/api/login` and anything under `/uploads/`, `/api/portal/` or
  `/api/public/` (`PUBLIC_PREFIXES`) requires a Bearer token** (`Authorization: Bearer <jwt>`)
  → else 401. Tokens are stateless **JWTs** (PyJWT, HS256) with `sub`/`iat`/`exp` claims, signed with
  `SECRET_KEY` (env; set it in production), valid 12h. `/api/login` returns the token. **Authorization is derived, not hand-wired**:
  `require_auth()` maps the URL's first path segment → resource (au1/au2/au3 → `admin_unit`) and the
  HTTP method → action (GET→read, POST→create, PUT/PATCH→update, DELETE→delete), then requires the
  `resource.action` permission on the user's role → else 403. For the survey/poll routes it first
  strips the `admin`/`portal` site segment (`SITE_PREFIXES`), then lets **later** path segments
  override both halves — `SUB_RESOURCE` (`.../questions/9/answers` → `form_result`,
  `.../news/41/blocks` → `news_block`) and
  `SUB_ACTION` (`POST .../publish` → `update`, not `create`). So **adding a new `/api/<resource>`
  route automatically needs `<resource>.{action}` permissions** — add the resource to
  `PERMISSION_RESOURCES` in `db.py` (which is the cross-product source for the seeded CRUD permissions).
  The one exception is `SELF_PATHS` / `SELF_PREFIXES` (`/api/change_password`, `/api/me`,
  `/api/me/...`, `/api/notifications...`): they still need a token but **no permission at all**,
  because they only ever touch `g.user`'s own row — a Зөвлөх мэргэжилтэн must be able to change
  their password and confirm their scope without being granted `user.*` over everybody, and
  every user must be able to read their own 🔔 inbox without `notification.read` (which is the
  *admin send* permission).
- **Error handling is centralized.** `register_error_handlers(app)` in `run.py` maps
  400/401/403/404/405/409/**422** to `{"error": ...}` JSON for the whole app — including unmatched-URL 404s and
  aborts raised inside any blueprint (Flask falls back to app-level handlers for blueprint errors).
- **Shared helpers**: `core/helpers.py` — `require(data, fields)` (→ 400), `json_body()`,
  `pick(data, fields)` (allowlist a body), `client_ip()`, `now_str()` (UTC
  `"YYYY-MM-DD HH:MM:SS"`), `page_params()` / `slice_page()` / `list_json()` and
  `register_error_handlers(target)`; `core/orm/query.py` — `paginate(stmt[, mappings])` and
  `get_or_404(model, key, msg)`. `admin/union/common.py` adds the union CRUD layer (`_list_rows`,
  `_get_one`, `_create`, `_update_by_id`, `_delete_by_id`, `_require_row`, `_check_ref`, …) over
  model classes.
- **Legacy schema code is frozen** (`core/db/schema*.py`, `migrate*.py`, `pg.py`, `pg_schema.py`):
  it is what migration 0001 runs and what upgrades a pre-Alembic database once. `_migrate()` /
  `_MIGRATIONS` / `_DROP_COLUMNS` are history now — add a new Alembic revision instead.
- **Uniqueness/parent checks are manual.** Creates verify the parent row exists (returning 400),
  then rely on a `try/except` around the INSERT to map PK/UNIQUE collisions to 409. There are no
  DB-level unique constraints beyond primary keys and a few `UNIQUE` columns (`permission.code`,
  `role.name`, `app_user.username`, `salary_scale.code`).
- **`org_stats_many()` computes derived member counts for a whole page in ONE `GROUP BY` query**
  (`org_stats()` is its single-id wrapper); `_role_perms_many()` does the same for role lists — no N+1.
  Before: **`org_stats()` (admin/union/organization.py) computed derived member counts** (total / female / under-35)
  via SQL on every `GET /api/organization`. Under-35 is computed live from `birth_date` using `julianday`.
- **Validated enums / field allowlists** live as module constants in the `admin/union/` module that uses them:
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
- **`member.member_status` and `member.status` are deliberately free text** (no lookup table, no
  enum) — `_validate_member()` only rejects a non-string / blank value with 400. Don't turn them
  into reference tables. They are three different things and all three are kept:
  `member_status` (ҮЭ-ийн гишүүний статус), `status` (бүртгэлийн төлөв) and the `is_active` 0/1 flag.
- **Every table carries `created_at` / `updated_at`, filled by SQLite triggers.**
  `_ensure_timestamps()` (db.py) runs at the end of `init_db()`: it walks `sqlite_master`, adds
  both columns wherever they are missing, and creates `trg_<table>_created` (AFTER INSERT) and
  `trg_<table>_updated` (AFTER UPDATE) for each one. That is why **no route sets them** — a new
  table or a new handler is stamped automatically. Two consequences worth knowing:
  `PRAGMA recursive_triggers` is OFF by default, which is what stops the trigger's own `UPDATE`
  from re-firing it; and the INSERT trigger uses `COALESCE(NEW.created_at, …)`, so the places that
  already write their own timestamps (`menu`, `page`, `form`, `user_scope`, `member_file`) keep
  winning. Rows that existed **before** the migration stay `NULL` — their real dates are unknown.
  A table rebuilt by a migration (`_drop_org_horoo`, `_relax_submission_user`) loses its triggers
  with the `DROP TABLE`; `_ensure_timestamps()` runs afterwards and puts them back, which is also
  why `_ORG_COLUMNS` lists the two columns — otherwise the rebuild would drop the values.
- **Registration codes are composed, not typed.** `school_category.id` is the leading **2 digits**
  (`printf('%02d', id)`, so ids are capped at 1–99 and `code` is derived, never stored; the seeded categories are numbered **11–17** so no zero-padding is visible) →
  `+ organization.org_code` (**3 digits**, hand-entered) = the organization's **5-digit** `full_code`
  → `+ member.union_card_code` (**4 digits**, hand-entered) = `member.union_card_number`, **9 digits**.
  Only the hand-entered parts are writable: `union_card_number` is derived, and a request that sets
  it directly gets a 400. `_digit_code()` enforces the exact digit counts; collisions return 409
  (both on the 5-digit org code and the 9-digit card number). Editing an organization's category or
  `org_code` calls `_recompute_cards()`, which rewrites every member's `union_card_number` in that
  organization — that's why `union_card_code` is stored as its own column.
- **Update routes accept `PUT` *and* `PATCH`** (`methods=["PUT", "PATCH"]`) — every one of them is
  already a partial update, and `auth.py` maps both to the `update` action. A wrong method now
  returns JSON 405 (`register_error_handlers`) instead of Flask's HTML page, so a frontend that
  used `PATCH` no longer fails silently.
- **`organization.school_category_id` is normalised before it is stored.** `_validate_org()` turns
  a form's `"12"` into `12` and an empty string into `NULL` (a string id would otherwise break the
  `f"{cat:02d}"` collision message and the code comparisons). `full_code` /
  `school_category_code` are `NULL` — not `"00…"` — when the category is missing, because
  `printf('%02d', NULL)` yields `'00'` (hence the `CASE` in `ORG_FULL_CODE_SQL`).
- **Reference FKs are validated, never free text.** `member.position_id` / `profession_id` /
  `salary_scale_id`, `member_reward.reward_type_id` and `organization.school_category_id`
  point at the reference tables;
  `_check_ref()` (admin/union/common.py) turns a bad id into a 400. Reads go through `MEMBER_SELECT` /
  `ORG_SELECT`, which LEFT JOIN the lookups so responses carry `position_name`, `profession_name`,
  `salary_scale_code`, `school_category_name`, etc. alongside the ids.
- **Four lookups carry a `code` next to the name** — `position`, `profession`, `reward_type` and
  `structure` are all `id`+`code`+`name`, so `admin/union/references.py` serves their CRUD through one set of shared
  helpers (`_ref_list/_ref_get/_ref_create/_ref_update/_ref_delete`, allowlist `CODED_REF_FIELDS`).
  `code` has **no DB-level UNIQUE** (SQLite cannot add one via `ALTER TABLE ADD COLUMN` on older
  DBs) — `_check_code_unique()` enforces it in code → 409. `PUT` is partial: send `code`, `name`
  or both. The seeds fill `code` with the 2-digit id (`01`, `02`, …); `_fill_ref_codes()` does the
  same once for pre-existing rows, guarded by `PRAGMA user_version = 2`. Deleting a lookup row that
  anything still points at is a **409** (see *Deleting a referenced row* below) — it used to NULL
  those columns silently (`REF_CLEAR_REFS`, removed).
- **`structure` (Бүтцийн удирдлага) is picked by two different tables** — `organization.structure_id`
  **and** `app_user.structure_id`, so it is the one lookup the client site and the admin site
  share. Both list endpoints filter by it (`GET /api/organization?structure_id=`,
  `GET /api/user?structure_id=`) and both reads join it for `structure_name` / `structure_code`
  (`ORG_SELECT`, `USER_SELECT`). Its 22 seeded rows come from the union's own structure table, and
  because the lookup is flat while the source is `I…V` sections with numbered units under them,
  `STRUCTURE_CODES` (db.py) carries the hierarchy in `code`: `II` is a section heading, `II.0` its
  unnumbered "Хариуцсан мэргэжилтэн" row, `II.3` the unit numbered 3 inside it. Four rows share the
  name "Хариуцсан мэргэжилтэн" — the `code` is what tells them apart.
- **A member's rewards live in `member_reward`** (`reward_type_id` + `description` + `reward_date`),
  the same one-member-many-rows pattern as `member_education`. `GET /api/member/<id>` embeds them
  as `rewards` (alongside `educations` / `contacts` / `files`); `GET /api/member_reward` filters by
  `?member_id=` / `?reward_type_id=` and LEFT JOINs the lookup for `reward_type_name` / `_code`.
- **Portal CMS** (`admin/content/`) is menu-driven. `menu.type` decides what a menu shows:
  `page` (fully dynamic content, admin-managed), `news`/`survey`/`poll`/`contact`/`home`
  (built-in features — the admin may rename/hide/reorder them but not change what they do),
  and `external` (jump to `external_url`, which is then required). Depth is capped at
  **2 levels** (`_check_parent()` rejects a grandchild). `slug` is unique and auto-derived from
  the title when omitted — `_slugify()` transliterates Cyrillic, `_unique_slug()` appends `-2`,
  `-3` on collision. Creating (or switching a menu to) `type='page'` auto-creates its empty
  `page` row via `_ensure_page()`. Deleting a menu cascades to sub-menus, `page` and blocks —
  `delete_menu()` first collects the subtree's file URLs with a recursive CTE so the bytes on
  disk go too.
- **Page content is a list of ordered blocks, not fixed slots.** `page_block` is polymorphic
  (same idea as `contact`): `type` ∈ `text`/`image`/`video`/`file`/`link`, and `BLOCK_FIELDS`
  (read by `_public_block()`) decides which columns belong to each type — responses only carry
  the relevant keys. The spec's `/api/page_image|page_file|page_video` routes are **thin typed
  views over the same table** (`_list_typed()` / `_insert_block()`), so images, files and videos
  share one `sort_order` sequence with the text blocks. `GET /api/page/<menu_id>` returns both
  `blocks` (everything, in order) and the filtered `images`/`files`/`videos` arrays. Video blocks
  echo their `url` as `youtube_url` for spec compatibility.
- **`/api/page` route ids differ by method** (this is what the spec asks for):
  `GET /api/page/<menu_id>` takes the **menu** id, `PUT /api/page/<id>` takes the **page** id.
- **Мэдээ (news) reuses the page-block idea on its own table.** `news` is the card (title,
  `category`, `author`, `cover_image_url`, `summary`, `status`) and `news_block` is the same
  polymorphic `text`/`image`/`video`/`file`/`link` block as `page_block` — so the frontend's
  block editor works for both without a rewrite. `category` is validated against
  `NEWS_CATEGORIES` (`Мэдээ` / `Сургалт`) → 400 (**the spec asks for 422; this repo answers 400
  everywhere and `register_error_handlers` has no 422 handler**). `status` walks
  `draft → published`, and the **server** stamps `published_at` on the first transition to
  `published` — a later unpublish/republish keeps the original date so the portal ordering does
  not jump. `DELETE` soft-deletes the item and its blocks (like every table).
- **A "Мэдээ" menu picks its category with `menu.news_category`.** `NULL` means *all* categories,
  so the seeded `news` menu keeps working; the admin creates one menu per category
  (`news_category='Мэдээ'` / `'Сургалт'`) and the portal calls
  `GET /api/portal/news?category=<that value>`. `_validate_menu()` rejects a `news_category` on
  any menu that is not `type='news'`. **Cyrillic query values must be percent-encoded** — a
  raw-bytes `?category=Мэдээ` (curl without `--data-urlencode`) reaches Flask mangled and gets a
  400; browsers and axios/fetch encode it automatically.
- **`portal_settings` is a singleton, not a resource.** One row for the whole system: no list,
  no id in the URL, just `GET` and `PUT`/`PATCH` on `/api/portal_settings`. `PUT` **overwrites
  the whole row** (fields you omit become `NULL` — the frontend knows every field), `PATCH`
  merges. `phones` is stored as a JSON string but is **always a list** in JSON (`_public()`),
  and at least one number is required. `map_embed_url` must contain `google.com/maps/embed`
  (it goes straight into an iframe `src`) and the other URL fields must start with `http(s)://`.
  `GET` **auto-creates** the row from `DEFAULT_PORTAL_SETTINGS` (db.py) when it is missing, so a
  fresh deploy needs no manual step. The portal reads it token-free at
  `/api/public/portal_settings` (and `/api/portal/portal_settings`, the same handler) —
  `/api/public/` is the read-only public namespace added to `PUBLIC_PREFIXES`.
- **Excel exports reuse the list query, never a second one.** `GET /api/member/export` and
  `/api/organization/export` (`admin/union/export.py`) call `member_list_query()` /
  `org_list_query()` — the exact `(sql, params)` the list endpoints page over, filters and
  **scope** included — so the file always matches the screen, just unpaged. Permission follows
  the usual path rule (`member.read`, `organization.read`); the survey file
  `GET /api/admin/forms/<id>/results/export` (`admin/forms/export.py`) needs `form_result.read`,
  the same as the results screen (the spec said `form.read`). It is the spec's option A: sheet
  "Хариултууд" (one row per submission, one column per question) + "Дүгнэлт" (`form_results()`
  written out). **No respondent column** — the results screen never identifies respondents and
  forms have no "named" flag, so the file may not either. `core/xlsx.py` writes with
  `constant_memory` to a temp file that is **unlinked right after it is opened** (the open handle
  streams it; nothing is left on disk even if a close hook never fires). Dates are real date
  cells, `None` is an empty cell, errors stay `{error}` JSON.
- **Хууль тогтоомж = the news pattern, not the page pattern.** One menu of type `legal`
  (added to `MENU_TYPES`) auto-lists `legal_document`; each row has its own id, no menu row per
  law. `display_mode`: `link` (`external_url` required, `http(s)://`), `file` (`pdf_url` required)
  or `detail` (portal page from `legal_document_block` — `text`/`file`/`link`, the page_block
  shapes; `pdf_url`, if set, is the primary PDF on top). Checks run on the merged row after a
  partial `PUT`/`PATCH`; `published_date` is stored `YYYY-MM-DD` (`YYYY.MM.DD` accepted). Order:
  `sort_order`, then `published_date DESC NULLS LAST`, then id. A replaced PDF leaves storage via
  `remove_upload()`; a deleted document/block keeps its files (soft delete). Permissions are `legal_document.*` for the
  blocks too: `PATH_RESOURCE["legal_document_block"]`, and `SUB_RESOURCE["blocks"]` is now a
  per-parent map (`{"news": "news_block"}`) — before, every `/blocks` path demanded
  `news_block.*`. These are the first tables created by an Alembic revision (0002) rather than
  the legacy DDL, so they have **no timestamp triggers**; their models set `created_at` /
  `updated_at` themselves (`default` / `onupdate`, same ISO format as the triggers). Portal search
  indexes them as `type="document"` (path: detail → `/legal/<id>`, link → `external_url`,
  file → `pdf_url`).
- **Portal search is Python-side, not SQL `LIKE`** (`core/search_core.py` + `client/search.py`).
  SQLite's `LIKE`/`lower()` only fold ASCII and Postgres `LIKE` is case-sensitive, so neither
  matches Cyrillic case-insensitively; instead `build_corpus()` loads everything the portal shows
  (published news + text blocks, visible `type='page'` menus whose chain is visible and whose
  `page.status='published'`, their blocks — `file` blocks become `type='document'` —, non-draft
  forms, visible partners) and matches with `str.lower()`. No `LIKE` means no wildcard injection.
  The corpus is rebuilt only when `_signature()` (COUNT + MAX(updated_at) of the 7 source tables,
  one query) changes, so a publish/delete shows up immediately — or when it is older than
  `CORPUS_MAX_AGE` (10 s), because `updated_at` has 1-second resolution and two edits in the
  same second leave the signature unchanged; identical requests are cached
  60 s per worker (`Cache-Control: max-age=60`). Page items get `path` from the menu slug chain
  (`/parent/child`) and block items `anchor = "block-<id>"` (the portal must render that id);
  a text block's title is its first `<h1-4>`. Snippets are HTML-escaped and only `<mark>` is
  added. Rate limit: 30 req/min per IP from **`X-Real-IP`** (nginx overwrites it; the first
  `X-Forwarded-For` hop is client-controlled) → 429 JSON; limits and caches are per gunicorn
  worker. `organization` results (optional in the spec) are not indexed.
- **Banner / partner (portal home page) share `core/home_core.py`.** Both tables carry
  `sort_order` + `is_visible` (0/1, returned as bool to the admin). `banner.image_url` is required
  and, like `link_url`, must be `http(s)://` or a relative path (`/uploads/...`) — any other scheme
  (`javascript:`) or `//host` is a 400; `partner.url` must be `http(s)://`. `starts_at`/`ends_at`
  are stored as **UTC** `"YYYY-MM-DD HH:MM:SS"` (an ISO value with `Z`/`+08:00` is converted, a
  naive one is taken as UTC — same as `scheduled_at`), so the public query compares them with
  `now_str()` as text; `NULL` = unbounded, and `ends_at < starts_at` is checked on the merged
  row after a partial `PUT`/`PATCH`. A replaced banner image leaves the disk through
  `remove_upload()` (a deleted one stays — soft delete) — and the same for `partner.logo_url` (Alembic 0003; optional, same
  `http(s)://`-or-relative rule; `IMAGE_FIELD` in `admin/home.py` maps each table to its image
  column). The two public lists are the only responses with a `Cache-Control` header.
- **News and settings images go through the existing `POST /api/upload`** — no new upload
  endpoint. `admin/news.py` and `admin/settings.py` import `remove_upload()` from
  `admin/content` (renamed from `_remove_upload`), so a replaced cover or a
  swapped logo takes its bytes off disk too (a deleted row keeps them — soft delete), and only ever under `UPLOAD_URL_PREFIX`.
- **The app server keeps no files and no log files** (production). `core/storage.py` is the one
  place that stores bytes: each area (`content`, `form`, `member`) is an `Area(area, local_dir)`
  with `save / delete / send / names`. When `S3_BUCKET` is set (production, in
  `/opt/edu-union/.env`) everything goes to `s3://$S3_BUCKET/uploads/<area>/<name>`; unset
  (local dev, tests) it falls back to the old `*_UPLOAD_DIR` folders, so tests and the on-disk
  layout are unchanged. **URLs in the DB never change** — `/uploads/content/<name>`,
  `/uploads/form/<name>` and `/api/member_file/<id>/download` still go through the app, which
  reads the object from S3 (≤ 20 MB, into memory) and answers with the same headers as before;
  the bucket stays fully private and member PDFs still need a token. Credentials come from the
  EC2 instance role via IMDS (hop limit 2 so the container can reach it) — no keys in code or
  `.env`. `tests/test_storage_s3.py` runs the S3 path against `moto`.
  Logs: `core/audit.py` writes one JSON line per request to **stdout** (`event, method, path,
  query, status, ms, user_id, username, ip` from `X-Forwarded-For`, `ua`; never bodies) plus
  `login` / `login_failed` events, and skips OPTIONS and the Docker healthcheck. gunicorn's own
  access log is off (`Dockerfile`). Docker's daemon-level `awslogs` driver ships stdout/stderr to
  CloudWatch group `/edu-union/app` (90-day retention). One-time AWS + server setup:
  `bash deploy/setup-s3-cloudwatch.sh` (bucket, log group, instance role, IMDS, `.env`,
  `daemon.json`, then `scripts/migrate_uploads_to_s3.py`) — run it **after** the S3-aware code is
  deployed. Query logs: `aws logs tail /edu-union/app --follow`, or Logs Insights on the JSON.
- **Portal uploads are two-step.** `POST /api/upload` (multipart, `file`) validates the extension
  and size — images (jpg/jpeg/png/webp) ≤ 5 MB, documents (pdf/doc/docx/xls/xlsx) ≤ 20 MB — saves
  to `CONTENT_UPLOAD_DIR` (`uploads/content/<uuid>.<ext>`) and returns `{url, name, mime_type,
  size}`; the caller stores that `url` on a block or on `page.cover_image`. The bytes are served
  back at `/uploads/content/<name>` **without a token** (a portal `<img src>` cannot send an
  Authorization header) — that's what `PUBLIC_PREFIXES` in `auth.py` is for. Uploading still
  needs `upload.create`. `remove_upload()` deletes a file from disk when its block/cover is
  replaced (not on delete — soft delete keeps it), and only ever touches paths under `UPLOAD_URL_PREFIX` (external URLs are
  left alone). **On Render the disk is ephemeral** — same persistent-disk caveat as member PDFs.
- **Мэдэгдэл is one notification plus a fan-out table** (`notification_api_spec.md`).
  `notifications` holds what was written; **sending** copies one `notification_recipients` row
  per addressee (`UNIQUE(notification_id, user_id)` + `INSERT OR IGNORE`, so sending twice is a
  no-op) and that row's `read_at` is the unread badge. `audience_type` is `all` (every **active**
  user), `role` (active users with that `role_id`) or `picked` — and because a *scheduled*
  `picked` notification must remember its list until send time, `audience_user_ids` stores it as
  a JSON string (the `user_scope.organization_ids` pattern; it is the one column beyond the
  spec's DDL). `POST` with no `scheduled_at` sends immediately (`status='sent'`), with one it
  waits (`status='scheduled'`), and an explicit `status='draft'` just saves — which is what makes
  the spec's own "only draft/scheduled may be deleted" rule reachable. A `sent` notification
  answers **422** on delete, with `?hard=1` as the deliberate escape hatch (same as
  `DELETE /api/admin/forms/<id>?hard=1`) — soft like every delete; the Postman collection uses it
  to clean up.
- **Scheduled notifications have no scheduler — `dispatch_due()` is called from two places.**
  There is no celery/APScheduler here and a background thread under `gunicorn --preload` would
  fan out once per worker, so `dispatch_due(conn)` (idempotent, and it claims each row with
  `UPDATE … WHERE status='scheduled'` so concurrent runs cannot double-send) is invoked by
  `scripts/send_due_notifications.py` (for cron) *and* lazily at the top of
  `GET /api/admin/notifications` and `GET /api/notifications`. **Cron is deliberately not
  installed** (decided 2026-09-17) — the lazy call is the whole mechanism in production, so a
  scheduled notification goes out the moment anybody opens the list or their inbox. In practice
  that is quick, because the admin layout's 🔔 polls the inbox on every page; the script stays in
  the repo for the day someone wants exact-minute delivery. Don't add a cron/timer, a background
  thread or an APScheduler job without asking. Timestamps are `now_str()`'s
  `"YYYY-MM-DD HH:MM:SS"`, which compares correctly as text, so `scheduled_at <= ?` is plain SQL.
- **The dashboard is one aggregate query set, and it obeys the scope** (`dashboard_api_spec.md`).
  `GET /api/admin/dashboard/summary` returns `total_members`, `total_organizations`,
  `by_category` and `gender`. `by_category` is driven by the **real `school_category` rows**, not
  a hard-coded six, and uses correlated subqueries so a category with no organizations still
  comes back as a zero row (id 17 has `short_name: null` — the spec allows serving it or hiding
  it, and this returns everything and lets the frontend choose). `gender` counts
  `member.gender` `'эр'`/`'эм'`, so the two need not add up to `total_members`. Every count runs
  through `scope_core`'s `org_condition()` / `member_condition()`, so a Зөвлөх мэргэжилтэн sees
  only their own schools' numbers with no extra query param — exactly like `/api/member`.
- **Санал хүсэлт / Өргөдөл гомдол are two plain tables, not an engine** (`feedback_api_spec.md`).
  `suggestions` (name/email/phone/**message**) and `complaints` (…/**description** + optional
  `file_url`/`file_name`) are the only **plural** table names in the schema — that is what the
  spec's DDL asks for, so `auth.py`'s `PATH_RESOURCE` maps them back to the singular permission
  resources `suggestion.*` / `complaint.*` (the same trick as `forms` → `form`).
  `feedback_core.KINDS` parameterizes the pair — one `validate()` / `list_page()` / `insert()`
  serves both tables, so the six routes are thin. The portal side is **token-free** (`/api/portal/`
  is in `PUBLIC_PREFIXES`) and returns `201 {status, id, message}` with a Mongolian confirmation;
  the admin side has **no "get one" route** (the list already carries `message`/`description`, so
  the 👁 modal reads what it already fetched) and **no status-change route** — the `status` column
  exists and stays `'new'`, which is what the spec asks for in V1. Validation is `400` everywhere
  (blank/missing field, e-mail shape, phone = 8 Mongolian digits after stripping `+976`, spaces
  and dashes, and the spec's `VARCHAR` lengths, which SQLite would otherwise ignore). A complaint's
  attachment goes through the existing `POST /api/upload`; `DELETE` hides the row and keeps
  the file (soft delete).
- **The survey / poll engine is one `form` table, not two features.** `form.type` is `survey`
  (судалгаа) or `poll` (санал асуулга — may carry PDFs); everything else — questions, options,
  submissions, results — is shared. `form.status` walks `draft → published → closed`
  (`POST .../publish` / `.../close`). Question types are fixed at four (`QUESTION_TYPES` in
  `forms_core.py`): `single_choice` / `multiple_choice` (need `form_option` rows) plus `scale`
  and `open_text`. `form_question.settings` is free-form JSON — `scale` gets `min`/`max`
  validated into it, and any extra keys the frontend needs (`min_label`, `placeholder`, …) pass
  through untouched.
- **The portal side is fully public.** `/api/portal/` is in `PUBLIC_PREFIXES`, so a visitor lists,
  opens and **submits** surveys with no token at all. When a token *is* sent, `_optional_user()`
  loads it without ever aborting (a bad token just means "guest"), so a logged-in submission is
  recorded under `form_submission.user_id` and `one_response` applies to it. **A guest submission
  stores `user_id = NULL` and is never deduplicated** — spec V1 explicitly rules out anonymous-vote
  and IP/device prevention. Don't put a UNIQUE index back on `(form_id, user_id)`: `one_response=0`
  and guest rows both need duplicates.
- **A form with answers is structurally frozen.** `_lock_if_answered()` (admin/forms/common.py) returns
  409 when a form already has submissions and someone tries to delete a question, delete/add an
  option, or change a question's type — old `form_answer_option` rows would otherwise lose meaning.
  Renaming an option label is always allowed (it doesn't move any answer). Deleting a form with
  answers only archives the form row (`deleted_at`, results stay readable); `?hard=1` deletes
  it with its questions/options/submissions — soft too, like every delete.
- **Result percentages are per-question, not per-form.** `_choice_results()` divides by the number
  of people who answered *that* question, so `multiple_choice` percentages sum past 100% by design.
  `_scale_results()` fills gaps in the 1..N range with zero counts so charts have no holes.
- **Poll PDFs mirror the member-PDF pattern**: validated (`.pdf` + `%PDF-` header, ≤20 MB, all
  files checked before any is saved), bytes under `FORM_UPLOAD_DIR` (`uploads/form/<uuid>.pdf`),
  metadata in `form_document`, served token-free from `/uploads/form/` for the portal's PDF viewer.
- **User management** (`admin/users/`): a `role` has many `permission`s (M:N via `role_permission`);
  an `app_user` picks one `role_id` and inherits all its permissions. A `role` also has an optional
  `code` (free text, blank → `NULL`); like the coded lookups it has **no DB-level UNIQUE** (older
  DBs got it via `ALTER TABLE ADD COLUMN`), so `_role_values()` (admin/users/roles.py) checks
  duplicates → 409. User reads carry it as `role_code` next to `role_name` (`USER_SELECT`). A user's name is stored
  **split** — `last_name` (Овог) + `first_name` (Нэр), like `member`. **`full_name` is gone**: not
  a column, not accepted on input, not returned. `_migrate_data()` splits an old `full_name` on the
  first space into the two columns before `_DROP_COLUMNS` removes it. Passwords are hashed with
  `generate_password_hash(..., method="pbkdf2")` (scrypt is unavailable in this Python build).
  `public_user()` strips `password_hash` from every response. Seed permissions are the cross-product
  of `PERMISSION_RESOURCES × PERMISSION_ACTIONS` (CRUD per resource) in `db.py`.
- **`user_scope` answers "which data", the role answers "which action"** (`user_scope_api_spec.md`).
  One row per `app_user` (`user_id` is the PK, `ON DELETE CASCADE`), reached at
  `GET|PUT|PATCH|DELETE /api/user/<id>/scope` and embedded as `scope` in `GET /api/user`,
  `GET /api/user/<id>` and `/api/login`, so the frontend never has to fan out per user.
  Two shapes share the table: a **Зөвлөх/Мэргэжилтэн** picks a `school_type` (`SCHOOL_TYPES` in
  `admin/users/common.py`: general/preschool/higher/vocational/science/rural) plus either
  `organization_ids` (only when `school_type='rural'` — ХОН) or `district_au2_code` (every other
  type); a **Сургуулийн менежер** picks a single `organization_id`. `_validate_scope()` enforces
  that split → 400, and checks the district against `admin_unit2` and every id against
  `organization`. `organization_ids` is stored as a JSON string but is **always a list** in JSON
  (`public_scope()`, now in `scope_core.py`). `PUT` overwrites the whole row, `PATCH` merges.
  Changing a user's `role_id` **deletes their scope row** — an old scope would otherwise be
  silently reused by a new role. No new permission: the routes sit under `/api/user/...`, so
  `user.read` / `user.update` / `user.delete` already cover them, and the same three handler
  bodies (`_scope_get` / `_scope_save` / `_scope_delete`) serve `/api/me/scope`, where the id
  comes from the token instead of the URL.
- **The scope is *enforced*, not just stored** (`scope_core.py`, `specialist_onboarding_api_spec.md`
  §5). `_org_where()` turns one `user_scope` row into a WHERE clause on `organization`:
  `organization_id` → that one school (Сургуулийн менежер); `school_type='rural'` →
  `organization_ids` (ХОН); any other `school_type` → `school_category_id` (via
  `SCHOOL_TYPE_CATEGORY`, which maps `preschool/general/vocational/higher/science` onto the
  **seeded ids 11–15**) **and** `au2_code = district_au2_code`. The filter hangs off the
  **scope row, not the role name** — admin (and anyone else without a row) gets `None` and sees
  everything, which is exactly the spec's "Admin болон бусад дүр → шүүлтгүй". `admin/union/`
  adds `org_condition()` / `member_condition()` to `GET /api/organization` / `GET /api/member`
  (so the frontend sends no extra query param) and calls `require_org_in_scope()` /
  `require_member_in_scope()` → **403** on the detail read and on every write. A rural scope with
  an empty `organization_ids` yields `0 = 1`, i.e. an empty list — not "everything".
  **Not extended to the sub-resources** (`member_education`, `member_reward`, `member_file`,
  `contact`, `salary_request`): a specialist with those permissions can still read them by
  `?member_id=`. The spec lists only member/organization; widening it is the next job.
- **Anх нэвтрэлт: `app_user.must_change_password` + `onboarding_completed_at`**
  (`specialist_onboarding_api_spec.md` §2-§4). Both columns default to **0/NULL**, so existing
  accounts (the seeded `admin` included) are never forced to change anything — `POST /api/user`
  writes `must_change_password = 1` **explicitly** for every account an admin creates.
  `POST /api/change_password` verifies `current_password` (wrong → **422**, the one place this
  repo answers 422) and clears the flag. `public_user()` returns both as booleans:
  `must_change_password`, plus `onboarding_completed`, which is **true for every role but
  Зөвлөх мэргэжилтэн** (matched on `role.name`, case/space-insensitively, by
  `scope_core.is_specialist()`) — nobody else has an onboarding step.
  `POST /api/me/onboarding/complete` stamps the date with `COALESCE`, so calling it twice keeps
  the first one and **no field is ever required** to be filled, by design.
- **An `organization` carries its own primary contact details** — `phone1`, `phone2`, `email`,
  `contact_name` are plain columns (the registration form fills them in directly). `contact` rows
  still work for an organization and are the way to record a *third* phone, a fax, or a second
  e-mail; the columns are the common case, the table is the overflow. `member` and `horoo` have
  no such columns — they go through `contact` only.
- **`contact` is polymorphic**: `owner_type` is `'horoo'`, `'organization'` or `'member'` (the value
  is also the table name), `owner_id` points into the matching table. This is how an owner gets
  **many** phones/faxes/emails — `member` has no single phone column. There is no FK on `contact`;
  ownership is validated in code on insert, and soft delete hides an owner's contacts with it
  (`POLYMORPHIC_OWNERS` in `core/orm/soft.py`); `_purge_orphan_contacts()` stays as a safety net.
- **Unicode**: `app.json.ensure_ascii = False` so Cyrillic is returned unescaped. Preserve this
  when touching JSON serialization config.

## Conventions

- Admin-unit codes are TEXT primary keys (e.g. `"011"`), preserved as strings with leading zeros.
- Union / user ids are INTEGER autoincrement; routes use `<int:...>` converters.
- List endpoints support optional filter query params (`?au1_code=`, `?holboo_id=`,
  `?horoo_id=` (horoo only), `?school_category_id=` (organization), `?organization_id=`, `?owner_type=&owner_id=`, `?resource=`, `?role_id=`, `?status=`).
  **Every other list endpoint is paginated on request**: send `?page=` and/or `?per_page=` and
  it answers `{items, total, page, per_page, pages}`; send neither and it still answers the plain
  array (the deployed frontend depends on that). `core/orm/query.paginate()` does COUNT +
  `LIMIT/OFFSET` in SQL (so per-row extras like `org_stats` run only for the page) and
  `slice_page()` handles lists filtered in Python (`/api/portal/forms?active=1`); `list_json()`
  picks the shape. Defaults 20 per page, capped at 100, `page<1` → 1, non-numeric → 400.
  `/api/menu?tree=1` is never paged, and `/api/me/organizations` keeps its `{items}` wrapper
  (meta is added when paged).
  The paginated list endpoints (`/api/admin/forms`, `/api/admin/news`, `/api/portal/news`,
  `/api/admin/suggestions`, `/api/admin/complaints`, `/api/admin/notifications`) also
  take `?search=&page=&per_page=`; **news answers in the news spec's shape**
  (`{data, total, per_page, current_page, pages}`), forms and feedback in the other
  (`{items, total, page, per_page, pages}`). `per_page` is capped at 100 and a non-numeric
  `page`/`per_page` is a 400.
- Imports are absolute (`from core.orm import session`, `from admin.union import bp`) and assume the repo
  root is on `sys.path` — always run from the repo root (`python run.py`).
