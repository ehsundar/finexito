#!/usr/bin/env bash
# Takes a fresh Ubuntu server to a running site. Run from your machine:
#
#   deploy/provision.sh <ssh-host> <domain>      e.g. deploy/provision.sh hetzner example.com
#
# Safe to re-run: every step checks before it changes anything, and an existing
# /opt/finexito/.env (with the database password the volume was created with) is
# never overwritten. Needs key-based root SSH to the host, and CI to have built
# images for origin/main.
set -euo pipefail

HOST=${1:?usage: provision.sh <ssh-host> <domain>}
DOMAIN=${2:?usage: provision.sh <ssh-host> <domain>}
APP_DIR=/opt/finexito
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

step "Base system: Docker, swap, firewall, key-only SSH"
remote 'bash -s' <<'EOF'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 unattended-upgrades >/dev/null
systemctl enable --now docker >/dev/null 2>&1

# Next's production build wants more than the 4 GB of a small box.
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
fi
grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab

ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw allow 443/udp >/dev/null
ufw --force enable >/dev/null

# Only reachable here over a key already, so passwords can safely go. The 00-
# prefix wins over cloud-init's 50-cloud-init.conf (sshd takes the first match).
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin prohibit-password\n' \
  >/etc/ssh/sshd_config.d/00-hardening.conf
sshd -t && systemctl reload ssh
EOF

step "Secrets in $APP_DIR/.env"
remote "bash -s" <<EOF
set -euo pipefail
mkdir -p $APP_DIR
f=$APP_DIR/.env
if [ -f \$f ]; then echo "exists, left untouched"; exit 0; fi
gen() { openssl rand -base64 48 | tr -d '/+=' | cut -c1-50; }
sed -E \
  -e "s|^SITE_ADDRESS=.*|SITE_ADDRESS=$DOMAIN|" \
  -e "s|^PUBLIC_ORIGIN=.*|PUBLIC_ORIGIN=https://$DOMAIN|" \
  -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$DOMAIN|" \
  -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=\$(gen)|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=\$(gen)|" \
  >\$f <<'TEMPLATE'
$(cat deploy/.env.example)
TEMPLATE
chmod 600 \$f
echo "generated"
EOF

step "Deploy"
make deploy DEPLOY_HOST="$HOST"

step "Done: https://$DOMAIN"
echo "Needs A/AAAA records for $DOMAIN and www.$DOMAIN pointing here (DNS only) for HTTPS."
echo "First admin: ssh $HOST 'cd $APP_DIR && docker compose exec backend python manage.py createsuperuser'"
