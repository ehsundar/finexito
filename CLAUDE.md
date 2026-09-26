# CLAUDE.md

## Rules

- Never mention Claude, Claude Code or Anthropic anywhere in this repository: not in commit messages (no `Co-Authored-By` trailers), PR descriptions, docs, code comments or any other files.
- Never commit or push unless explicitly asked to.
- Each deployment is a white-labelled product built from the same apps. Never hard-code a product name (in code, emails, UI or docs aimed at users); read Django's `SITE_NAME` setting, which the frontend gets from `/api/v1/site/`.
- Production secrets and settings live in GitHub, on the `production` environment: secrets for anything sensitive, variables for the rest. CI writes the server's `.env` from them on every deploy, so never edit `/opt/finexito/.env` by hand or generate secrets on the server. A new setting is a key in `deploy/.env.example` plus a GitHub secret or variable of the same name.
