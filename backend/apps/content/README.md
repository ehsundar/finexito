# content

A small CMS: Markdown pages written in the admin and rendered by the frontend
at `/pages/<slug>`.

## Model

`Page` extends `common.models.BaseModel`, so it has a UUID primary key,
timestamps and `extra`.

| Field          | Meaning                                                          |
| -------------- | ---------------------------------------------------------------- |
| `title`        | Required; surrounding whitespace is trimmed.                     |
| `slug`         | Unique, letters/digits/`-`/`_`. The page's address.              |
| `summary`      | Optional, up to 300 characters, for listings and link previews.  |
| `body`         | Markdown (see [Writing](#writing)). Up to 100,000 characters.    |
| `visibility`   | `public` (anyone) / `private` (signed-in members only).          |
| `status`       | `draft` / `published`. A published page must have a body.        |
| `published_at` | Stamped on first publish. Set it in the future to schedule.      |

A page is live when it is `published` **and** `published_at` has passed.
Drafts and scheduled pages are `404` to everyone, including staff; preview them
by publishing as `private`.

Validation lives in `Page.clean()`, so the admin enforces it. Code that writes
pages directly should call `full_clean()` first.

## Writing

Create a page at `/api/admin/content/page/add/`; the slug fills itself from
the title. Link to it as `/pages/<slug>` (the admin's *View on site* goes there).

The body is [GitHub-flavoured Markdown](https://github.github.com/gfm/):
headings, emphasis, ~~strikethrough~~, links, images, lists, task lists
(`- [x]`), block quotes, code blocks, tables and horizontal rules.

Fenced code blocks are highlighted when they name a language (` ```python `);
an unknown language, or none, renders as plain code.

**Raw HTML is not rendered** — it shows up as text. Links and images only keep
`http(s)`, `mailto` and relative URLs; anything else (`javascript:` and the
like) is dropped. So the body is safe to render whoever wrote it.

## API — `/api/v1/`

| Method | Path            | Purpose                                                        |
| ------ | --------------- | -------------------------------------------------------------- |
| GET    | `pages/`        | Live pages the caller may see, without `body`. `?visibility=`. |
| GET    | `pages/{slug}/` | One live page, with `body`.                                    |

Both allow anonymous callers. A private page returns `401` with
*Sign in to read this page.* to an anonymous caller, so the frontend can send
them to sign in; the body is never included. There is no write API: pages are
edited in the admin.

## Where things live

| File             | What                                                   |
| ---------------- | ------------------------------------------------------ |
| `models.py`      | `Page`, `PageVisibility`, `PageStatus`, validation     |
| `serializers.py` | Summary (listing) vs. full page                        |
| `views.py`       | `PageViewSet`                                          |
| `admin.py`       | The editor                                             |

The renderer is `frontend/src/components/markdown/`.

## Rendering: decisions

The frontend renders bodies with **react-markdown** (the unified/remark/rehype
pipeline), on the server. Features are added as plugins in that pipeline rather
than by switching renderers.

| Need                | Choice                                  | Status  |
| ------------------- | --------------------------------------- | ------- |
| Markdown + GFM      | `react-markdown` + `remark-gfm`         | Done    |
| Code highlighting   | Shiki (`@shikijs/rehype`), server-side  | Done    |
| Custom widgets      | `remark-directive` + a component registry | Planned |
| Uploaded images     | An `Asset` model; storage to be decided  | Planned |

**Code highlighting — Shiki.** It uses VS Code's grammars and themes and runs
on the server, so pages arrive already coloured and the browser loads no
highlighter. One highlighter is shared per server process; languages load on
first use. It carries both a light and a dark theme, switched in CSS.

**Widgets — directives, not MDX or Markdoc.** Widgets (callouts, chips, icons…)
will be written as `:::callout{type=warning} … :::` or `::chip[New]`, each name
mapped to a React component with validated attributes. An unknown or invalid
widget falls back to its raw text.

- *MDX* was rejected: it compiles content into JavaScript that runs, the wrong
  trust model for content typed into an admin.
- *Markdoc* is safe and schema-validated, but means replacing the renderer, a
  different tag syntax and losing the remark/rehype plugin ecosystem. Worth
  revisiting only if widgets grow complex enough to need its validation.

**Images.** Linked images (`![alt](https://…)`) already work. Uploads need
somewhere to live: media is not served in production yet. The options are a
server volume served by Caddy (simplest, but must be backed up) or S3-compatible
storage via `django-storages` (durable, but needs credentials).
