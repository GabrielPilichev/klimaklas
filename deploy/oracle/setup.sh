#!/usr/bin/env bash
# Инсталира КлимаКлас на чист Ubuntu 24.04 сървър (Oracle Cloud Always Free, ARM или AMD).
# Може да се пуска многократно – при повторно пускане само обновява кода и рестартира.
#
#   curl -fsSL https://raw.githubusercontent.com/GabrielPilichev/klimaklas/main/deploy/oracle/setup.sh -o setup.sh
#   bash setup.sh klimaklas.duckdns.org
set -euo pipefail

DOMAIN="${1:?Употреба: bash setup.sh <домейн>   (напр. klimaklas.duckdns.org)}"
REPO="${KK_REPO:-https://github.com/GabrielPilichev/klimaklas.git}"
DIR=/opt/klimaklas

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "1/6 Swap файл (за да не свърши паметта при сборката на малките машини)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

say "2/6 Docker и Git"
if ! command -v docker >/dev/null; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose-v2 git netfilter-persistent iptables-persistent
  sudo systemctl enable --now docker
fi

say "3/6 Защитна стена на сървъра: отваряме 80 и 443"
# Ubuntu образите на Oracle имат iptables правило REJECT, което блокира всичко освен SSH.
for rule in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 443"; do
  # shellcheck disable=SC2086
  sudo iptables -C INPUT $rule -m state --state NEW -j ACCEPT 2>/dev/null ||
    sudo iptables -I INPUT 1 $rule -m state --state NEW -j ACCEPT
done
sudo netfilter-persistent save >/dev/null

say "4/6 Код от GitHub"
if [ -d "$DIR/.git" ]; then
  sudo git -C "$DIR" pull --ff-only
else
  sudo git clone --depth 1 "$REPO" "$DIR"
fi

say "5/6 Настройки (.env)"
if [ ! -f "$DIR/.env" ]; then
  sudo tee "$DIR/.env" >/dev/null <<EOF
KK_DOMAIN=$DOMAIN
POSTGRES_PASSWORD=$(openssl rand -hex 24)
KK_SECRET_KEY=$(openssl rand -hex 32)
KK_DEMO_PASSWORD=${KK_DEMO_PASSWORD:-KlimaKlas-2026}
KK_TELEGRAM_BOT_TOKEN=
KK_TELEGRAM_CHAT_ID=
KK_SMTP_HOST=
EOF
  sudo chmod 600 "$DIR/.env"
else
  sudo sed -i "s/^KK_DOMAIN=.*/KK_DOMAIN=$DOMAIN/" "$DIR/.env"
fi

say "6/6 Сборка и стартиране (първия път отнема 5–10 минути)"
cd "$DIR"
sudo docker compose up -d --build
for _ in $(seq 1 60); do
  sudo docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" 2>/dev/null && break
  sleep 2
done
sudo docker compose exec -T backend python -m app.seed

say "Готово! Отворете https://$DOMAIN"
echo "Ако страницата не се отваря: проверете DNS записа и Ingress правилата (80/443) в Oracle Cloud."
