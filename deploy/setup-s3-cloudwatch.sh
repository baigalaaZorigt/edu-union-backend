#!/usr/bin/env bash
# Файл -> S3, лог -> CloudWatch: НЭГ УДААГИЙН тохиргоо (идемпотент — дахин ажиллуулж болно).
# Локал дээрээс, AWS admin эрх + EC2-ийн SSH түлхүүртэйгээр:   bash deploy/setup-s3-cloudwatch.sh
#
# ӨМНӨ НЬ: S3 дэмжлэгтэй код (core/storage.py, scripts/migrate_uploads_to_s3.py) серверт
# deploy хийгдсэн байх ёстой (main руу push -> pipeline). S3_BUCKET өгөхгүй бол тэр код
# хуучин шигээ диск рүү бичдэг тул эхэлж deploy хийхэд аюулгүй.
#
# Юу хийх вэ:
#   1. S3 bucket (private: public access бүрэн хаалттай, SSE-S3 шифрлэлт)
#   2. CloudWatch log group /edu-union/app (хадгалах хугацаа RETENTION_DAYS)
#   3. EC2 instance role: зөвхөн энэ bucket-ийн uploads/* + энэ log group руу бичих эрх
#   4. IMDS hop limit 2 — docker контейнер instance role-оо ашиглаж чадна
#   5. Сервер дээр: .env-д S3_BUCKET, docker-ийн анхдагч лог драйвер = awslogs,
#      хуучин файлуудыг S3 руу зөөж, контейнерийг шинээр асаана
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="${REGION:-ap-northeast-1}"
INSTANCE_ID="${INSTANCE_ID:-i-03648c2bcc4e19350}"
HOST="${HOST:-ec2-user@13.196.178.202}"
KEY="${KEY:-edu-union-key.pem}"
LOG_GROUP="${LOG_GROUP:-/edu-union/app}"
RETENTION_DAYS="${RETENTION_DAYS:-90}"
ROLE=edu-union-ec2

aws() { command aws --region "$REGION" "$@"; }
say() { echo; echo "==> $*"; }
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${BUCKET:-edu-union-uploads-$ACCOUNT}"
say "Account $ACCOUNT | $REGION | bucket $BUCKET | log group $LOG_GROUP"

say "1/5 S3 bucket"
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "байна"
else
  aws s3api create-bucket --bucket "$BUCKET" \
    --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
  echo "үүслээ"
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

say "2/5 CloudWatch log group"
if [ "$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
      --query "length(logGroups[?logGroupName=='$LOG_GROUP'])" --output text)" = "0" ]; then
  aws logs create-log-group --log-group-name "$LOG_GROUP"
  echo "үүслээ"
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days "$RETENTION_DAYS"

say "3/5 EC2 instance role"
POLICY=$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["s3:PutObject","s3:GetObject","s3:DeleteObject"],
  "Resource":"arn:aws:s3:::$BUCKET/uploads/*"},
 {"Effect":"Allow","Action":"s3:ListBucket","Resource":"arn:aws:s3:::$BUCKET",
  "Condition":{"StringLike":{"s3:prefix":["uploads/*"]}}},
 {"Effect":"Allow","Action":["logs:CreateLogStream","logs:PutLogEvents","logs:DescribeLogStreams"],
  "Resource":["arn:aws:logs:$REGION:$ACCOUNT:log-group:$LOG_GROUP","arn:aws:logs:$REGION:$ACCOUNT:log-group:$LOG_GROUP:*"]}]}
JSON
)
ASSOC="$(aws ec2 describe-iam-instance-profile-associations \
  --filters "Name=instance-id,Values=$INSTANCE_ID" "Name=state,Values=associated" \
  --query 'IamInstanceProfileAssociations[0].IamInstanceProfile.Arn' --output text)"
if [ "$ASSOC" != "None" ]; then
  TARGET_ROLE="$(aws iam get-instance-profile --instance-profile-name "${ASSOC##*/}" \
    --query 'InstanceProfile.Roles[0].RoleName' --output text)"
  echo "инстанс аль хэдийн profile-тэй -> '$TARGET_ROLE' role-д policy нэмнэ"
else
  TARGET_ROLE="$ROLE"
  if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
    aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
      "Version":"2012-10-17","Statement":[{"Effect":"Allow",
      "Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  fi
  if ! aws iam get-instance-profile --instance-profile-name "$ROLE" >/dev/null 2>&1; then
    aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
    aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
    sleep 10                                    # IAM тархах хугацаа
  fi
  aws ec2 associate-iam-instance-profile --instance-id "$INSTANCE_ID" \
    --iam-instance-profile "Name=$ROLE" >/dev/null
  echo "'$ROLE' profile инстанст залгагдлаа (дахин асаах шаардлагагүй)"
fi
aws iam put-role-policy --role-name "$TARGET_ROLE" --policy-name edu-union-s3-logs \
  --policy-document "$POLICY"

say "4/5 IMDS hop limit 2 (контейнерээс instance role ашиглах)"
aws ec2 modify-instance-metadata-options --instance-id "$INSTANCE_ID" \
  --http-endpoint enabled --http-put-response-hop-limit 2 >/dev/null
sleep 15                                         # role-ийн эрх IMDS-д хүрэх хугацаа

say "5/5 Сервер: .env, docker awslogs, файл зөөх, контейнер шинэчлэх"
ssh -i "$KEY" -o ConnectTimeout=20 "$HOST" "sudo bash -s" <<REMOTE
set -euo pipefail
ENV=/opt/edu-union/.env
for kv in "S3_BUCKET=$BUCKET" "AWS_REGION=$REGION"; do
  k="\${kv%%=*}"
  if grep -q "^\$k=" "\$ENV"; then sed -i "s|^\$k=.*|\$kv|" "\$ENV"; else echo "\$kv" >> "\$ENV"; fi
done

# docker-ийн анхдагч лог драйвер -> CloudWatch (хост дээр лог файл үлдэхгүй)
python3 - <<'PY'
import json, os
p = "/etc/docker/daemon.json"
cfg = json.load(open(p)) if os.path.exists(p) else {}
cfg["log-driver"] = "awslogs"
cfg["log-opts"] = {"awslogs-region": "$REGION", "awslogs-group": "$LOG_GROUP",
                   "tag": "{{.Name}}", "mode": "non-blocking", "max-buffer-size": "4m"}
json.dump(cfg, open(p, "w"), indent=2)
PY
systemctl restart docker

cd /opt/edu-union/app
echo "-- хуучин файлууд -> S3"
docker compose run --rm --no-deps -T app python scripts/migrate_uploads_to_s3.py
docker compose up -d --force-recreate
for _ in \$(seq 1 30); do
  [ "\$(docker inspect -f '{{.State.Health.Status}}' edu-union-app)" = healthy ] && break; sleep 5
done
echo "-- дахин (хооронд нь орсон файл байвал)"
docker compose run --rm --no-deps -T app python scripts/migrate_uploads_to_s3.py
echo "лог драйвер: \$(docker inspect -f '{{.HostConfig.LogConfig.Type}}' edu-union-app)"
docker ps --format '{{.Names}} {{.Status}}'
REMOTE

say "Бэлэн. Шалгах:"
echo "  aws --region $REGION logs tail $LOG_GROUP --follow"
echo "  aws --region $REGION s3 ls s3://$BUCKET/uploads/ --recursive | head"
echo "Хуучин локал файлууд /opt/edu-union/data дотор ҮЛДСЭН — шалгасны дараа гараар устгана."
