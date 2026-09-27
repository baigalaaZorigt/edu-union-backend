#!/usr/bin/env bash
# Төслийн чанарын шалгалт — стандарт, lint, тест. Repo-ийн үндсээс ажиллуулна.
#
#   bash scripts/check.sh            # lint + бүтцийн дүрэм + pytest
#   bash scripts/check.sh --fast     # pytest-гүй (зөвхөн статик шалгалт)
#   bash scripts/check.sh --pg       # + Postgres: migration, model drift, Postman ×2 (docker, newman)
#
# Claude Code-ийн `/quality` skill (.claude/skills/quality) үүнийг ашигладаг.
# Алдаа гарвал 1-ээр гарна; бүх шалгалт ажиллаж дуусаад дүгнэлтээ хэвлэнэ.
set -uo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python )}
FAST=0; PG=0
for a in "$@"; do
  case $a in --fast) FAST=1 ;; --pg) PG=1 ;; *) echo "үл мэдэх сонголт: $a"; exit 2 ;; esac
done
FAILED=()
step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
fail() { echo "  ✗ $1"; FAILED+=("$1"); }
ok()   { echo "  ✓ $1"; }

# ---------------------------------------------------------------- lint
step "Lint (ruff: E9 синтакс, F pyflakes, B bugbear — ruff.toml)"
if $PY -m ruff check . ; then ok "ruff"; else fail "ruff check"; fi

# ---------------------------------------------------------------- стандарт
step "Стандарт — бүтцийн дүрмүүд (CLAUDE.md)"

big=$(git ls-files '*.py' | xargs wc -l | awk '$1 > 300 && $2 != "total" {print "    " $2 " (" $1 " мөр)"}')
if [ -z "$big" ]; then ok ".py файл бүр ≤ 300 мөр"; else echo "$big"; fail "300 мөрөөс урт файл (багц болгож хуваа)"; fi

sql=$(grep -rnE '\btext\(|exec_driver_sql|\.execute\(\s*f?["'\'']' admin client core run.py scripts --include='*.py' \
      | grep -v -e '^core/db/' -e '^core/orm/models/' -e '^scripts/migrate_to_pg.py' -e 'PRAGMA')
if [ -z "$sql" ]; then ok "SQL текстгүй — бүх query ORM-оор"; else echo "$sql"; fail "SQL текст app кодод (ORM ашигла)"; fi

cross=$(grep -rnE '^\s*(from|import) admin(\.|\s|$)' client core --include='*.py')
if [ -z "$cross" ]; then ok "client/, core/ нь admin/-аас импортлохгүй"; else echo "$cross"; fail "client/core → admin импорт (core/ руу зөөнө)"; fi

unreg=""
for f in $(grep -rl 'Blueprint(' admin client --include='*.py'); do
  mod=${f%.py}; mod=${mod%/__init__}; mod=${mod//\//.}
  grep -qE "^from $mod import bp\b" run.py || unreg+="    $mod"$'\n'
done
if [ -z "$unreg" ]; then ok "Blueprint бүр run.py-д бүртгэлтэй"; else printf '%s' "$unreg"; fail "бүртгэгдээгүй blueprint (run.py)"; fi

tq=$(grep -rnE 'select\(\*[A-Za-z]+\.__table__\.c' admin client core --include='*.py' | grep -v 'select_from' )
missing=""
while IFS= read -r line; do
  [ -z "$line" ] && continue
  file=${line%%:*}; n=$(echo "$line" | cut -d: -f2)
  sed -n "${n},$((n+15))p" "$file" | grep -q 'select_from(' || missing+="    $file:$n"$'\n'
done <<< "$tq"
if [ -z "$missing" ]; then ok "select(*Model.__table__.c) бүр .select_from(Model)-тэй (soft delete шүүлт)"
else printf '%s' "$missing"; fail "__table__.c select-д .select_from(Model) алга"; fi

# ---------------------------------------------------------------- тест
if [ $FAST = 0 ]; then
  step "pytest"
  if $PY -m pytest tests -q -p no:logging 2>&1 | tail -3 | grep -v '^{"ts"'; [ "${PIPESTATUS[0]}" = 0 ]; then
    ok "pytest"; else fail "pytest"; fi
fi

# ---------------------------------------------------------------- Postgres
if [ $PG = 1 ]; then
  step "Postgres: migration + model drift + Postman ×2"
  PORT_DB=5431; PORT_APP=5091; NAME=eu-check-pg
  TMP=$(mktemp -d); trap 'pkill -f "127.0.0.1:$PORT_APP" 2>/dev/null; docker rm -f $NAME >/dev/null 2>&1; rm -rf "$TMP"' EXIT
  docker rm -f $NAME >/dev/null 2>&1
  docker run -d --name $NAME -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=eu -p $PORT_DB:5432 postgres:17-alpine </dev/null >/dev/null
  for _ in $(seq 30); do docker exec $NAME pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done; sleep 2
  export DATABASE_URL=postgresql://postgres:pw@127.0.0.1:$PORT_DB/eu
  if $PY -c "from core.db.bootstrap import ensure_seeded; ensure_seeded()" >/dev/null; then ok "alembic upgrade head + seed"
  else fail "migration/seed"; fi
  drift=$($PY - <<'EOF'
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import core.orm.models  # noqa: F401
from core import orm
from core.orm.base import Base
with orm.engine().connect() as c:
    print(len(compare_metadata(MigrationContext.configure(c), Base.metadata)))
EOF
)
  if [ "$drift" = 0 ]; then ok "model ↔ DB зөрүү 0"; else fail "model drift: $drift (alembic revision хэрэгтэй)"; fi
  UPLOAD_DIR=$TMP/m CONTENT_UPLOAD_DIR=$TMP/c FORM_UPLOAD_DIR=$TMP/f \
    $PY -m gunicorn run:app --preload -w 2 --bind 127.0.0.1:$PORT_APP >"$TMP/srv.log" 2>&1 &
  for _ in $(seq 30); do curl -sf -o /dev/null http://127.0.0.1:$PORT_APP/api/public/portal_settings && break; sleep 1; done
  for i in 1 2; do
    out=$(npx --no-install newman run docs/edu-union-backend.postman_collection.json \
          --env-var base_url=http://127.0.0.1:$PORT_APP 2>/dev/null)
    echo "$out" | grep -E '│\s+(requests|assertions)' | sed 's/^/    /'
    echo "$out" | grep -E '^\s+inside "' | sed 's/^/    /'
    if echo "$out" | grep -qE '│\s+assertions\s+│\s+[0-9]+\s+│\s+0\s+│'; then ok "Postman ажиллуулалт $i"
    else fail "Postman ажиллуулалт $i"; fi
  done
  n500=$(grep -c '"status": 500' "$TMP/srv.log")
  if [ "$n500" = 0 ]; then ok "серверийн лог 500-гүй"; else fail "серверт $n500 удаа 500"; fi
  unset DATABASE_URL
fi

# ---------------------------------------------------------------- дүгнэлт
echo
if [ ${#FAILED[@]} = 0 ]; then printf '\033[32mБүх шалгалт давлаа.\033[0m\n'; exit 0; fi
printf '\033[31m%d шалгалт унасан:\033[0m\n' "${#FAILED[@]}"; printf '  - %s\n' "${FAILED[@]}"; exit 1
