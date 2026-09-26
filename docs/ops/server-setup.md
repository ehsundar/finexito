# Setting up the production server

How to go from nothing to your domain (`example.com` below) running on a Hetzner Cloud
server. Most of it is automated by `make provision`; this guide covers the
steps around it that happen in web consoles, and the traps along the way.

What you end up with:

```
Internet -> Caddy :80/:443 -> /api/* -> backend  (Django, gunicorn)
                           -> /*     -> frontend (Next.js standalone) -> backend
                              db (Postgres 17, not exposed)
```

All in Docker Compose, from [`deploy/`](../../deploy/README.md), with HTTPS
certificates handled by Caddy.

## Before you start

- An SSH key on your machine (`~/.ssh/id_ed25519.pub`). Create one with
  `ssh-keygen -t ed25519` if needed.
- The GitHub CLI logged in (`gh auth login`), with admin access to
  `ehsundar/finexito`, for the Actions secrets below.
- A Hetzner Cloud account and a Cloudflare account holding the domain.

## 1. Create the server

1. In the Hetzner Cloud console, go to **Security -> SSH Keys -> Add SSH key**
   and paste the output of `cat ~/.ssh/id_ed25519.pub`.
2. **Add Server**: image **Ubuntu**, newest LTS. 2 vCPU / 4 GB is enough.
3. Under **SSH Keys**, **tick your key**. This is the step that matters.

> **The key must be chosen at creation.** A *Rebuild* reuses only the keys the
> server was created with, and ignores keys you add to the project later,
> even a default key. A server created without your key accepts no SSH login:
> Ubuntu refuses root passwords over SSH (`PermitRootLogin prohibit-password`),
> so resetting the root password in the console doesn't help either.
>
> **If you're locked out**, use Rescue rather than deleting the server:
> 1. **Rescue -> Enable rescue**, choose `linux64`, and tick your key.
> 2. **Power -> Power cycle.** Rescue only applies to the next boot. The
>    SSH banner changes from `OpenSSH ... Ubuntu` to `... Debian` once you're in
>    rescue: `nc <ip> 22`.
> 3. `ssh root@<ip>`, then:
>    ```bash
>    mount /dev/sda1 /mnt
>    cat >> /mnt/root/.ssh/authorized_keys   # paste your public key, then Ctrl-D
>    umount /mnt && reboot
>    ```

## 2. Add an SSH alias

In `~/.ssh/config`, above any `Host *` block:

```
Host hetzner
  HostName <server IPv4>
  User root
```

Check it with `ssh hetzner hostname`. If it complains about a changed host key
after a rebuild, clear the old one with `ssh-keygen -R <server IPv4>`.

Then check `/root/.ssh/authorized_keys` on the server. It should hold only
keys you recognise.

## 3. Point the domain at it

In Cloudflare, go to **DNS -> Records** and add:

| Type | Name  | Content            | Proxy status |
| ---- | ----- | ------------------ | ------------ |
| A    | `@`   | server IPv4        | DNS only     |
| AAAA | `@`   | server IPv6        | DNS only     |
| A    | `www` | server IPv4        | DNS only     |
| AAAA | `www` | server IPv6        | DNS only     |

The IPv6 address is on the server's page in Hetzner, or run
`ssh hetzner ip -6 addr show scope global`.

> **Keep it DNS only (grey cloud).** Caddy gets its own certificate from
> Let's Encrypt, which needs traffic to reach the server directly. If you turn
> the Cloudflare proxy on later, set **SSL/TLS -> Full (strict)** first or you
> will get redirect loops.
>
> `.dev` domains are HTTPS-only in every browser, so the site shows nothing
> until the certificate is issued in the next step.

Check the records have propagated before going on:

```bash
dig +short A example.com @1.1.1.1
```

## 4. Provision

From the repo:

```bash
make provision                     # defaults: DEPLOY_HOST=hetzner DOMAIN=ehsandar.dev
make provision DEPLOY_HOST=other DOMAIN=example.com
```

[`deploy/provision.sh`](../../deploy/provision.sh) then:

1. installs Docker and Compose, adds 2 GB swap (the Next.js build needs it on
   4 GB), sets up `ufw` to allow only 22/80/443, turns off SSH password login and
   keeps unattended security upgrades on;
2. writes `/opt/finexito/.env` from `.env.example`, with the domain filled in
   and a freshly generated `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`;
3. runs `make deploy`: copies `compose.yml` and the `Caddyfile` over and brings
   the stack up on CI's images for the tip of `main`, migrating first and
   waiting for it to report healthy.

CI must have built images for that commit, so push and let the Deploy Action
build before the first provision.

Caddy requests the certificate as soon as it starts, which usually takes a few
seconds.

It is safe to run again at any time. Every step checks first, and an existing
`.env` is **never overwritten**, because Postgres keeps the password it
was first created with. If you lose that file, you lose access to the data.

## 5. Check it

```bash
curl -I https://example.com/api/healthz/        # 200
curl -I http://example.com/                     # 308 -> https://
curl -I https://www.example.com/                # 301 -> https://example.com/
ssh hetzner 'cd /opt/finexito && docker compose ps'
```

If HTTPS fails, Caddy's log says why. It is almost always DNS not pointing at
the server yet, or the Cloudflare proxy being on:

```bash
ssh hetzner 'cd /opt/finexito && docker compose logs caddy | grep -i certificate'
```

## 6. First admin

```bash
ssh hetzner
cd /opt/finexito
docker compose exec backend python manage.py createsuperuser
```

Admin: `https://example.com/api/admin/`.

## From here on

- **Releasing:** push to `main`; the *Deploy* GitHub Action runs `make deploy`
  for that commit. By hand, `make deploy` ships the tip of `main`,
  `make deploy IMAGE_TAG=<older sha>` rolls back, and `make logs` follows the logs.
- **Everyday commands, backups and restores:** see
  [`deploy/README.md`](../../deploy/README.md).
- **Moving to a new server:** copy the old `/opt/finexito/.env` to the same
  path on the new server before provisioning, then restore the latest
  backup. That keeps the same secret key, so existing sign-ins stay valid.

## Deploying from GitHub Actions

`.github/workflows/deploy.yml` runs `make deploy` on every push to `main`, over
SSH as root with a key of its own. Secrets are not part of it: they live only
in `/opt/finexito/.env` on the server. To rotate `DJANGO_SECRET_KEY`, edit it
there and run `make deploy`; everyone is signed out, but no data is lost.

1. Make a key just for CI and authorise it on the server:

   ```bash
   ssh-keygen -t ed25519 -N '' -C github-actions-deploy -f /tmp/gha_deploy
   ssh hetzner "cat >> ~/.ssh/authorized_keys" < /tmp/gha_deploy.pub
   ```

2. Add it to a `production` environment on the repo:

   ```bash
   gh secret set DEPLOY_SSH_KEY     --env production < /tmp/gha_deploy
   gh secret set DEPLOY_KNOWN_HOSTS --env production --body "$(ssh-keyscan -t ed25519 <server IPv4>)"
   gh secret set DEPLOY_HOST        --env production --body <server IPv4>
   gh secret set DEPLOY_USER        --env production --body root
   rm /tmp/gha_deploy /tmp/gha_deploy.pub
   ```

## Worth doing afterwards

- **Copy backups off the server.** They sit on the same disk as the database.
- **Cloudflare:**
  - **Email -> Email Routing** to receive `you@example.com` in another inbox.
  - A DMARC record: `TXT _dmarc "v=DMARC1; p=none; rua=mailto:you@example.com"`.
  - CAA records allowing `letsencrypt.org` **and** `sectigo.com`. Caddy
    falls back to ZeroSSL, which issues through Sectigo.
  - DNSSEC.
  - 2FA on the account.
- **Raise HSTS:** set `SECURE_HSTS_SECONDS=31536000` in `/opt/finexito/.env` once
  HTTPS has been stable for a while.
