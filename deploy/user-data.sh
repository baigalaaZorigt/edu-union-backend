#!/bin/bash
# EC2-ийн эхний ачаалалт (cloud-init user-data). Amazon Linux 2023.
# provision.sh нь __ХУВЬСАГЧ__ хэсгүүдийг бодит утгаар нь солиод илгээнэ.
#
# Юу суулгах вэ: docker + compose plugin, git, nginx, certbot.
# Юу ажиллуулах вэ: аппын контейнер (RDS руу хандана) + nginx урвуу прокси.
set -euxo pipefail
exec > >(tee -a /var/log/edu-union-bootstrap.log) 2>&1

REPO="__REPO__"
APP_DIR=/opt/edu-union/app
DOMAIN="__DOMAIN__"

dnf -y update
dnf -y install docker git nginx

# docker compose (plugin) — AL2023-ийн репод байхгүй тул шууд татна
mkdir -p /usr/local/lib/docker/cli-plugins
ARCH=$(uname -m); case "$ARCH" in aarch64) C=aarch64 ;; *) C=x86_64 ;; esac
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${C}" \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
# buildx — AL2023-ийн docker багцад ОРООГҮЙ, гэхдээ `compose build` шаарддаг
BX_ARCH=$([ "$ARCH" = aarch64 ] && echo arm64 || echo amd64)
curl -fsSL "$(curl -s https://api.github.com/repos/docker/buildx/releases/latest \
             | grep -o "https://[^\"]*linux-${BX_ARCH}" | head -1)" \
     -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-buildx

systemctl enable --now docker
usermod -aG docker ec2-user

# ---- Аппын код ба тохиргоо ----
mkdir -p /opt/edu-union/data
git clone --depth 1 "$REPO" "$APP_DIR" || (cd "$APP_DIR" && git pull --ff-only)

cat > /opt/edu-union/.env <<'ENVEOF'
DATABASE_URL=__DATABASE_URL__
SECRET_KEY=__SECRET_KEY__
CORS_ORIGINS=*
ENVEOF
chmod 600 /opt/edu-union/.env

cd "$APP_DIR"
docker compose up -d --build

# ---- nginx ----
install -m 644 deploy/nginx.conf /etc/nginx/conf.d/edu-union.conf
if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "none" ]; then
  sed -i "s/server_name  _;/server_name  ${DOMAIN};/" /etc/nginx/conf.d/edu-union.conf
fi
# AL2023-ийн анхдагч server блок 80 портыг эзэлдэг тул унтраана
sed -i 's/^\( *\)listen       80;/\1listen       8080;/; s/^\( *\)listen       \[::\]:80;/\1listen       [::]:8080;/' /etc/nginx/nginx.conf || true
nginx -t && systemctl enable --now nginx && systemctl reload nginx

# ---- certbot (HTTPS) ----
# AL2023-д багц байхгүй тул албан ёсны зөвлөмжөөр venv-д суулгана.
python3 -m venv /opt/certbot
/opt/certbot/bin/pip install --upgrade pip
/opt/certbot/bin/pip install certbot certbot-nginx
ln -sf /opt/certbot/bin/certbot /usr/bin/certbot
# Гэрчилгээг АВТОМАТААР шинэчлэх (өдөрт 2 удаа шалгана)
cat > /etc/systemd/system/certbot-renew.service <<'EOF'
[Unit]
Description=Certbot renew
[Service]
Type=oneshot
ExecStart=/opt/certbot/bin/certbot renew --quiet --nginx --post-hook "systemctl reload nginx"
EOF
cat > /etc/systemd/system/certbot-renew.timer <<'EOF'
[Unit]
Description=Certbot renew twice a day
[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=1h
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now certbot-renew.timer

# Домэйн өгсөн бол гэрчилгээг ШУУД авна (DNS нь энэ IP рүү заасан байх ёстой).
if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "none" ]; then
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
          --register-unsafely-without-email --redirect || \
    echo "certbot амжилтгүй — DNS бэлэн болсны дараа гараар: certbot --nginx -d $DOMAIN"
fi

echo "BOOTSTRAP OK $(date -Is)"
