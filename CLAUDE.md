# CLAUDE.md

## Rules

- Never mention Claude, Claude Code or Anthropic anywhere in this repository: not in commit messages (no `Co-Authored-By` trailers), PR descriptions, docs, code comments or any other files.
- Never commit or push unless explicitly asked to.
- Each deployment is a white-labelled product built from the same apps. Never hard-code a product name (in code, emails, UI or docs aimed at users); read Django's `SITE_NAME` setting, which the frontend gets from `/api/v1/site/`.
- Production secrets and settings live in GitHub, on the `production` environment: secrets for anything sensitive, variables for the rest. CI writes the server's `.env` from them on every deploy, so never edit `/opt/finexito/.env` by hand or generate secrets on the server. A new setting is a key in `deploy/.env.example` plus a GitHub secret or variable of the same name.

## Writing code

Write the simplest thing that works: the least code, the fewest files, the fewest moving parts. Every layer has to earn its place.

- Don't build what a maintained package already does.
- Don't add machinery "just in case" (extra processes, background loops, fallbacks, options); add it when there is a real need.
- Keep the calling side plain: using a feature should be as ordinary as saving a model, not calling a helper that wraps it.
- Behaviour lives with the data: on the model, or at the one place it is used. No modules that exist only to hold helper functions.
- Don't keep code paths for things that are not in use.
- Do include the small things almost always needed: a new model gets a useful admin (list columns, filters, search, read-only where code owns the data, and an action for the obvious operation, like retrying a failure), and a migration. Stop there; don't grow features nobody asked for.
- Stay within what was asked; ask before widening scope, and keep commits to one topic.
