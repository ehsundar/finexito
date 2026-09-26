#!/usr/bin/env bash
# The server's one fixed entry point, installed at /opt/finexito/bin/entry. The
# Deploy Action's SSH key is pinned to it; `make deploy` and provision.sh call it
# as root. The command comes from SSH_ORIGINAL_COMMAND, or from the arguments:
#
#   sync-env         read KEY=value lines from stdin into shared/.env, then stop.
#                    Only the keys listed in `managed` are accepted.
#   release <sha>    deploy that commit of main: its deploy/ files and CI's images
#                    tagged <sha>. `release main` takes the tip of main.
#   rollback         redeploy the release that was live before the current one.
#
# Layout under /opt/finexito:
#   repo.git/        bare mirror of GitHub; fetched, never checked out
#   shared/.env      secrets and site config, kept across releases
#   releases/<sha>/  deploy/ from that commit, with shared/.env linked in
#   current          the live release; `previous` the one before it
#
# A successful release installs its own copy of this script, so changes to it
# ship like everything else.
set -euo pipefail

ROOT=/opt/finexito
KEEP=5
cd "$ROOT"

die() { echo "$*" >&2; exit 1; }

sync_env() {
  local managed=" DJANGO_SECRET_KEY RESEND_API_KEY " key value tmp
  while IFS='=' read -r key value; do
    [ -n "$key" ] || continue
    case "$managed" in *" $key "*) ;; *) echo "ignoring unmanaged key: $key" >&2; continue ;; esac
    [ -n "$value" ] || die "empty value for $key"
    tmp=$(mktemp)
    grep -v "^$key=" shared/.env >"$tmp" || true
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
    install -m 600 "$tmp" shared/.env && rm -f "$tmp"
    echo "set $key"
  done
}

# Runs a release's own deploy.sh against the images built for its commit.
run() { (cd "releases/$1" && IMAGE_TAG=$1 ./deploy.sh); }

# Points `current` at a release that has just come up, keeping the old one as
# `previous`, then syncs the host-level files it ships.
promote() {
  local sha=$1 was
  was=$(basename "$(readlink current 2>/dev/null)" 2>/dev/null || true)
  if [ -n "$was" ] && [ "$was" != "$sha" ]; then ln -sfn "releases/$was" previous; fi
  ln -sfn "releases/$sha" current
  install -m 644 current/finexito-backup.cron /etc/cron.d/finexito-backup
  prune
  install -m 755 current/entry.sh bin/entry
}

prune() {
  local keep_current keep_previous dir
  keep_current=$(readlink -f current)
  keep_previous=$(readlink -f previous 2>/dev/null || true)
  ls -1dt releases/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r dir; do
    dir=$(readlink -f "$dir")
    [ "$dir" = "$keep_current" ] || [ "$dir" = "$keep_previous" ] || rm -rf "$dir"
  done
}

release() {
  local sha=${1:?usage: release <sha>|main} tmp was
  git -C repo.git fetch -q origin '+refs/heads/main:refs/heads/main'
  [ "$sha" = main ] && sha=$(git -C repo.git rev-parse main)
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || die "bad commit: $sha"
  git -C repo.git merge-base --is-ancestor "$sha" main || die "$sha is not on main"

  if [ ! -d "releases/$sha" ]; then
    mkdir -p releases
    tmp=$(mktemp -d releases/.incoming.XXXXXX)
    git -C repo.git archive "$sha:deploy" | tar -x -C "$tmp"
    ln -s ../../shared/.env "$tmp/.env"
    mv "$tmp" "releases/$sha"
  fi

  echo "==> releasing $sha"
  if run "$sha"; then
    promote "$sha"
    echo "==> $sha is live"
    return
  fi

  was=$(basename "$(readlink current 2>/dev/null)" 2>/dev/null || true)
  if [ -n "$was" ] && [ "$was" != "$sha" ]; then
    echo "==> $sha failed, restoring $was" >&2
    run "$was" || echo "==> restoring $was failed too" >&2
  fi
  exit 1
}

rollback() {
  local to
  to=$(basename "$(readlink previous 2>/dev/null)" 2>/dev/null || true)
  [ -n "$to" ] && [ -d "releases/$to" ] || die "no previous release"
  echo "==> rolling back to $to"
  run "$to"
  promote "$to"
}

read -r cmd arg _ <<<"${SSH_ORIGINAL_COMMAND:-$*}" || true
case "${cmd:-}" in
  sync-env) sync_env ;;
  release) release "${arg:-}" ;;
  rollback) rollback ;;
  *) die "usage: sync-env | release <sha>|main | rollback" ;;
esac
