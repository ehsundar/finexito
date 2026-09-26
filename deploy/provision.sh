#!/usr/bin/env bash
# Takes a fresh Ubuntu server to a running site. Run from your machine:
#
#   deploy/provision.sh <ssh-host> <domain>      e.g. deploy/provision.sh hetzner example.com
#
# Safe to re-run: every step checks before it changes anything. Needs key-based
# root SSH to the host, CI to have built images for origin/main, and the server's
# .env, which only the Deploy Action writes, from the production environment's
# secrets and variables in GitHub.
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

step "Deploy"
if ! remote "test -f $APP_DIR/.env"; then
  echo "No $APP_DIR/.env yet. Set the production secrets and variables in GitHub, then:"
  echo "  gh workflow run deploy.yml"
  exit 0
fi
make deploy DEPLOY_HOST="$HOST"

step "Done: https://$DOMAIN"
echo "Needs A/AAAA records for $DOMAIN and www.$DOMAIN pointing here (DNS only) for HTTPS."
echo "First admin: ssh $HOST 'cd $APP_DIR && docker compose exec backend python manage.py createsuperuser'"
