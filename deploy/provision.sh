#!/usr/bin/env bash
# Takes a fresh Ubuntu server to a running site. Run from your machine:
#
#   deploy/provision.sh <ssh-host> <domain>      e.g. deploy/provision.sh myserver example.com
#
# Safe to re-run: every step checks before it changes anything, and an existing
# shared/.env (with the database password the volume was created with) is never
# overwritten. A server still on the old git-checkout layout is moved over to
# releases, keeping its .env. Needs key-based root SSH to the host and an authenticated `gh`.
set -euo pipefail

HOST=${1:?usage: provision.sh <ssh-host> <domain>}
DOMAIN=${2:?usage: provision.sh <ssh-host> <domain>}
REPO=${REPO:-ehsundar/finexito}
APP_DIR=/opt/finexito

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

step "Base system: Docker, swap, firewall, key-only SSH"
remote 'bash -s' <<'EOF'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 git unattended-upgrades >/dev/null
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

step "Read-only GitHub deploy key"
remote 'test -f ~/.ssh/deploy_finexito || ssh-keygen -q -t ed25519 -N "" -C "finexito-deploy@$(hostname)" -f ~/.ssh/deploy_finexito'
pubkey=$(remote 'cat ~/.ssh/deploy_finexito.pub')
key_body=$(awk '{print $2}' <<<"$pubkey")
if gh repo deploy-key list -R "$REPO" | grep -qF "$key_body"; then
  echo "already registered on $REPO"
else
  tmp=$(mktemp) && echo "$pubkey" >"$tmp"
  gh repo deploy-key add "$tmp" -R "$REPO" --title "$HOST $(remote hostname) (read-only)"
  rm -f "$tmp"
fi

step "Mirror of $REPO at $APP_DIR/repo.git"
remote "bash -s" <<EOF
set -euo pipefail
grep -q 'Host github.com' ~/.ssh/config 2>/dev/null ||
  printf 'Host github.com\n  IdentityFile ~/.ssh/deploy_finexito\n  IdentitiesOnly yes\n' >>~/.ssh/config
grep -q '^github.com ' ~/.ssh/known_hosts 2>/dev/null || ssh-keyscan -t ed25519 github.com 2>/dev/null >>~/.ssh/known_hosts
mkdir -p $APP_DIR/bin $APP_DIR/shared $APP_DIR/releases
[ -d $APP_DIR/repo.git ] || git clone -q --bare git@github.com:$REPO.git $APP_DIR/repo.git
git -C $APP_DIR/repo.git fetch -q origin '+refs/heads/main:refs/heads/main'
git -C $APP_DIR/repo.git log -1 --oneline main
EOF

step "Retire the old git checkout, if this server still has one"
remote "bash -s" <<EOF
set -euo pipefail
cd $APP_DIR
[ -d .git ] || { echo "none"; exit 0; }
if [ -f deploy/.env ] && [ ! -f shared/.env ]; then install -m 600 deploy/.env shared/.env; fi
[ -f shared/.env ] || { echo "no deploy/.env to carry over; leaving the checkout alone" >&2; exit 1; }
sed -i 's|command="$APP_DIR/deploy/deploy.sh"|command="$APP_DIR/bin/entry"|' ~/.ssh/authorized_keys
rm -f /etc/cron.d/finexito-backup
find . -mindepth 1 -maxdepth 1 ! -name bin ! -name shared ! -name releases ! -name repo.git \
  ! -name current ! -name previous -exec rm -rf {} +
echo "retired; .env kept in shared/, CI key now pinned to bin/entry"
EOF

step "Secrets in $APP_DIR/shared/.env"
remote "bash -s" <<EOF
set -euo pipefail
f=$APP_DIR/shared/.env
if [ -f \$f ]; then echo "exists, left untouched"; exit 0; fi
gen() { openssl rand -base64 48 | tr -d '/+=' | cut -c1-50; }
git -C $APP_DIR/repo.git show main:deploy/.env.example | sed -E \
  -e "s|^SITE_ADDRESS=.*|SITE_ADDRESS=$DOMAIN|" \
  -e "s|^PUBLIC_ORIGIN=.*|PUBLIC_ORIGIN=https://$DOMAIN|" \
  -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$DOMAIN|" \
  -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=\$(gen)|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=\$(gen)|" \
  >\$f
chmod 600 \$f
echo "generated"
EOF

step "Entry point at $APP_DIR/bin/entry"
remote "git -C $APP_DIR/repo.git show main:deploy/entry.sh >$APP_DIR/bin/entry && chmod 755 $APP_DIR/bin/entry && echo installed"

step "Release the tip of main (pull images, migrate, start)"
remote "$APP_DIR/bin/entry release main"

step "Done: https://$DOMAIN"
echo "Needs A/AAAA records for $DOMAIN and www.$DOMAIN pointing here (DNS only) for HTTPS."
echo "First admin: ssh $HOST 'cd $APP_DIR/current && docker compose exec backend python manage.py createsuperuser'"
