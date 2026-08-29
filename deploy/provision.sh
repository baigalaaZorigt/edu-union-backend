#!/usr/bin/env bash
# edu-union-backend — AWS дээрх бүтэн дэд бүтцийг үүсгэнэ (идемпотент).
#
#   RDS (Postgres, хамгийн жижиг)  <-- зөвхөн EC2-оос ба таны IP-ээс
#   EC2 (Amazon Linux 2023)        --> docker (апп) + nginx + certbot
#
# Ажиллуулах:
#     bash deploy/provision.sh
# Сонголтууд (орчны хувьсагчаар):
#     DOMAIN=api.example.mn   — өгвөл nginx-д бичигдэж, certbot гэрчилгээ авна
#     REGION=ap-northeast-1   — AWS бүс
#     DB_PASSWORD=...         — өгөөгүй бол автоматаар үүснэ
#
# Дахин ажиллуулахад аюулгүй: аль хэдийн байгаа нөөцийг дахин үүсгэхгүй.
set -euo pipefail

REGION="${REGION:-ap-northeast-1}"
NAME="${NAME:-edu-union}"
REPO="${REPO:-https://github.com/baigalaaZorigt/edu-union-backend.git}"
DOMAIN="${DOMAIN:-api.fmesu.mn}"   # DNS-ийн A бичлэг EC2 рүү заасан байх ёстой
# Браузерээс хандахыг зөвшөөрөх эхүүд (порталын домэйнууд). "*" биш байх нь зөв.
CORS_ORIGINS="${CORS_ORIGINS:-https://fmesu.mn,https://www.fmesu.mn}"

DB_ID="${NAME}-db"
DB_NAME=eduunion
DB_USER=eduadmin
DB_CLASS="${DB_CLASS:-db.t3.micro}"     # хамгийн жижиг (free tier)
EC2_TYPE="${EC2_TYPE:-t3.micro}"        # хамгийн жижиг (free tier)
KEY_NAME="${NAME}-key"
KEY_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/${KEY_NAME}.pem"
WEB_SG_NAME="${NAME}-web-sg"
DB_SG_NAME="${NAME}-db-sg"
BACKUP_DAYS="${BACKUP_DAYS:-7}"         # RDS автомат нөөцлөлтийг хэдэн хоног хадгалах

aws() { command aws --region "$REGION" "$@"; }
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "Бүс: $REGION | Домэйн: $DOMAIN"
MYIP="$(curl -s https://checkip.amazonaws.com | tr -d '\n')"
VPC="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
echo "    VPC: $VPC | таны IP: $MYIP"

# ---------------------------------------------------------------- SG (web)
say "Security group — вэб (22/80/443)"
WEB_SG="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$WEB_SG_NAME" \
          --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [ -z "$WEB_SG" ] || [ "$WEB_SG" = "None" ]; then
  WEB_SG="$(aws ec2 create-security-group --group-name "$WEB_SG_NAME" \
            --description "edu-union app server" --vpc-id "$VPC" --query GroupId --output text)"
fi
aws ec2 authorize-security-group-ingress --group-id "$WEB_SG" --protocol tcp --port 22  --cidr "$MYIP/32"   >/dev/null 2>&1 || true
aws ec2 authorize-security-group-ingress --group-id "$WEB_SG" --protocol tcp --port 80  --cidr 0.0.0.0/0    >/dev/null 2>&1 || true
aws ec2 authorize-security-group-ingress --group-id "$WEB_SG" --protocol tcp --port 443 --cidr 0.0.0.0/0    >/dev/null 2>&1 || true
echo "    $WEB_SG"

# ---------------------------------------------------------------- SG (db)
say "Security group — өгөгдлийн сан (5432)"
DB_SG="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$DB_SG_NAME" \
         --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [ -z "$DB_SG" ] || [ "$DB_SG" = "None" ]; then
  DB_SG="$(aws ec2 create-security-group --group-name "$DB_SG_NAME" \
           --description "edu-union postgres" --vpc-id "$VPC" --query GroupId --output text)"
fi
# Зөвхөн аппын серверээс (SG-ээр) ба нүүлгэлт хийх таны IP-ээс
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" --protocol tcp --port 5432 \
    --source-group "$WEB_SG" >/dev/null 2>&1 || true
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" --protocol tcp --port 5432 \
    --cidr "$MYIP/32" >/dev/null 2>&1 || true
echo "    $DB_SG"

# ---------------------------------------------------------------- key pair
say "SSH түлхүүр"
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  aws ec2 create-key-pair --key-name "$KEY_NAME" --query KeyMaterial --output text > "$KEY_FILE"
  chmod 400 "$KEY_FILE"
  echo "    шинээр үүсгэв: $KEY_FILE"
else
  echo "    аль хэдийн байна: $KEY_NAME (файл: $KEY_FILE)"
fi

# ---------------------------------------------------------------- RDS
say "RDS Postgres ($DB_CLASS, нөөцлөлт ${BACKUP_DAYS} хоног)"
if ! aws rds describe-db-instances --db-instance-identifier "$DB_ID" >/dev/null 2>&1; then
  DB_PASSWORD="${DB_PASSWORD:-$(python3 -c 'import secrets,string;a=string.ascii_letters+string.digits;print("".join(secrets.choice(a) for _ in range(28)))')}"
  echo "$DB_PASSWORD" > "$(dirname "$KEY_FILE")/.db_password"
  chmod 600 "$(dirname "$KEY_FILE")/.db_password"
  aws rds create-db-instance \
    --db-instance-identifier "$DB_ID" \
    --db-instance-class "$DB_CLASS" \
    --engine postgres --engine-version "${PG_VERSION:-17.6}" \
    --master-username "$DB_USER" --master-user-password "$DB_PASSWORD" \
    --db-name "$DB_NAME" \
    --allocated-storage 20 --storage-type gp3 --storage-encrypted \
    --no-multi-az --publicly-accessible \
    --backup-retention-period "$BACKUP_DAYS" \
    --preferred-backup-window 18:00-18:30 \
    --preferred-maintenance-window sun:19:00-sun:19:30 \
    --vpc-security-group-ids "$DB_SG" \
    --auto-minor-version-upgrade --copy-tags-to-snapshot \
    --tags Key=project,Value=edu-union-backend \
    --query 'DBInstance.DBInstanceIdentifier' --output text
  echo "    үүсгэв — бэлэн болтол хүлээж байна (5-10 мин) ..."
else
  DB_PASSWORD="${DB_PASSWORD:-$(cat "$(dirname "$KEY_FILE")/.db_password" 2>/dev/null || true)}"
  echo "    аль хэдийн байна: $DB_ID"
fi
aws rds wait db-instance-available --db-instance-identifier "$DB_ID"
DB_HOST="$(aws rds describe-db-instances --db-instance-identifier "$DB_ID" \
           --query 'DBInstances[0].Endpoint.Address' --output text)"
echo "    endpoint: $DB_HOST"

if [ -z "${DB_PASSWORD:-}" ]; then
  echo "!! DB нууц үг олдсонгүй (deploy/.db_password). DB_PASSWORD=... өгч дахин ажиллуулна уу." >&2
  exit 1
fi
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}"

# ---------------------------------------------------------------- EC2
say "EC2 аппын сервер ($EC2_TYPE)"
IID="$(aws ec2 describe-instances --filters "Name=tag:Name,Values=${NAME}-app" \
        "Name=instance-state-name,Values=pending,running" \
        --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || true)"
if [ -z "$IID" ] || [ "$IID" = "None" ]; then
  AMI="$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
         --query 'Parameter.Value' --output text)"
  SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
  UD="$(mktemp)"
  sed -e "s|__REPO__|$REPO|g" \
      -e "s|__DATABASE_URL__|$DATABASE_URL|g" \
      -e "s|__SECRET_KEY__|$SECRET_KEY|g" \
      -e "s|__DOMAIN__|$DOMAIN|g" \
      -e "s|__CORS_ORIGINS__|$CORS_ORIGINS|g" \
      "$(dirname "${BASH_SOURCE[0]}")/user-data.sh" > "$UD"
  IID="$(aws ec2 run-instances --image-id "$AMI" --instance-type "$EC2_TYPE" \
        --key-name "$KEY_NAME" --security-group-ids "$WEB_SG" \
        --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3,DeleteOnTermination=true}' \
        --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
        --user-data "file://$UD" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${NAME}-app},{Key=project,Value=edu-union-backend}]" \
        --query 'Instances[0].InstanceId' --output text)"
  rm -f "$UD"
  echo "    үүсгэв: $IID"
else
  echo "    аль хэдийн ажиллаж байна: $IID"
fi
aws ec2 wait instance-running --instance-ids "$IID"
IP="$(aws ec2 describe-instances --instance-ids "$IID" \
      --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"

cat <<EOF

============================================================
  БЭЛЭН
============================================================
  EC2      : $IID   ($IP)
  RDS      : $DB_HOST:5432/$DB_NAME  (нөөцлөлт ${BACKUP_DAYS} хоног)
  SSH      : ssh -i "$KEY_FILE" ec2-user@$IP
  Апп      : http://$IP/api/portal/forms
  Bootstrap: ssh ... 'sudo tail -f /var/log/edu-union-bootstrap.log'

  Дараагийн алхам:
   1) Өгөгдлөө зөөх (энэ машинаас):
        DATABASE_URL="$DATABASE_URL" python3 migrate_to_pg.py
   2) Домэйн: A бичлэгийг $IP рүү заагаад серверт:
        sudo certbot --nginx -d api.example.mn
============================================================
EOF
