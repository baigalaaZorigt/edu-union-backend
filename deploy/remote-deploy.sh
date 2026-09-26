#!/usr/bin/env bash
# EC2 дээр ажиллах deploy (root-оор — AWS SSM Run Command дуудна, .github/workflows/deploy.yml).
#
#   bash deploy/remote-deploy.sh <prev_commit>
#
# Код аль хэдийн origin/main руу шилжсэн байна (workflow-ийн SSM команд fetch + reset хийгээд
# энэ скриптийг ШИНЭ кодоос нь ажиллуулна). <prev_commit> нь буцаах (rollback) цэг.
#
# Дараалал — алхам бүр амжилтгүй бол сайт хуучин контейнер дээрээ үлдэнэ:
#   1. хуучин image-ийг :previous гэж хадгална
#   2. шинэ image build (хуучин контейнер ажилласаар)
#   3. ensure_seeded() — ТҮР контейнерт, swap-аас ӨМНӨ (gunicorn --preload унавал сайт унана)
#   4. swap (docker compose up -d) → healthy болохыг хүлээнэ
#   5. healthy болохгүй бол :previous image + <prev_commit> руу буцаана
set -euo pipefail

APP=/opt/edu-union/app
IMAGE=edu-union-backend
PREV_COMMIT="${1:-}"
cd "$APP"
git() { command git -c safe.directory="$APP" "$@"; }

say() { echo; echo "==> $*"; }

rollback() {
  say "ROLLBACK: $1"
  if docker image inspect "$IMAGE:previous" >/dev/null 2>&1; then
    docker tag "$IMAGE:previous" "$IMAGE:latest"
  fi
  if [ -n "$PREV_COMMIT" ]; then
    git reset --hard "$PREV_COMMIT" || true
  fi
  docker compose up -d
  exit 1
}

say "Код: $(git log --oneline -1)"

say "1/5 Хуучин image-ийг :previous болгон хадгалах"
docker tag "$IMAGE:latest" "$IMAGE:previous" 2>/dev/null || echo "(хуучин image алга — анхны deploy)"

say "2/5 Build"
docker compose build || rollback "build амжилтгүй"

say "3/5 ensure_seeded() — түр контейнерт"
docker compose run --rm --no-deps app \
  python -c "from core.db import ensure_seeded; ensure_seeded(); print('ensure_seeded OK')" \
  || rollback "ensure_seeded амжилтгүй (схем/migration)"

say "4/5 Swap"
docker compose up -d

status=""
for _ in $(seq 1 30); do                       # ≤ 150 сек
  status="$(docker inspect -f '{{.State.Health.Status}}' edu-union-app 2>/dev/null || echo missing)"
  [ "$status" = healthy ] && break
  sleep 5
done
[ "$status" = healthy ] || rollback "контейнер healthy болсонгүй (төлөв: $status)"

say "5/5 Шалгалт + цэвэрлэгээ"
curl -fsS -o /dev/null -w "portal/forms -> %{http_code}\n" http://127.0.0.1:8000/api/portal/forms
docker image prune -f >/dev/null
docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
say "Deploy амжилттай: $(git log --oneline -1)"
