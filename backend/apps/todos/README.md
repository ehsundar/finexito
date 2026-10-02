# todos

A personal task manager: an Inbox, projects, sections, tasks and sub-tasks,
priorities, labels, built-in filters and search, with one-line quick add. It is
optional: take `apps.todos` out of `INSTALLED_APPS` (and its settings import)
and it is gone. The full spec is [docs/prd/todos/1-core.md](../../../docs/prd/todos/1-core.md).

## Models

| Model            | What |
| ---------------- | ---- |
| `Project`        | A member's project; nests 3 levels. One per member is the Inbox (`is_inbox`), made the first time it is asked for (`Project.objects.inbox(user)`), and can't be renamed, archived, nested or deleted. |
| `Section`        | A heading inside one project. |
| `Task`           | In a project, optionally in one of its sections, optionally under another task; nests 4 levels. |
| `Label`          | A member's tag; names are unique per member, case-insensitively. |
| `FavouriteFilter`| A member's pin of a built-in filter's slug. |

Each level is its own model with its own rules in `clean()`, and the API saves
through `full_clean()`, so the admin and the API enforce the same ones:

- Archiving a project archives its sub-projects; unarchiving brings them back.
  An archived project or section hides its tasks.
- Moving a section to another project takes its tasks. A sub-task lives in
  its parent's project and section: nesting a task brings it there, and moving
  a task moves its sub-tasks. Moving a task to another project or section
  un-nests it.
- New rows, and rows moved somewhere new, go to the end of their siblings.
- `Task.close()` completes a task and its open sub-tasks. `Task.reopen()`
  reopens it, the sub-tasks completed with it, and any completed parents.
- `extra` is any JSON object up to `TODOS_MAX_EXTRA_BYTES`, stored as is.

Colours are names (`Colour`), not hex values; the frontend maps each to a
theme variable.

## Filters

`filters.py`. Each filter is a `Filter` subclass with a `slug`, a `name` and
`queryset(user)`; defining the class registers it.

## Quick add

`POST todos/tasks/quick/` with `{"text": …}`, plus optionally the `project`,
`section`, `parent` or `labels` of the view it was opened from. `parse_quick_add` in
`views.py` reads `#Project`, `/Section`, `@label` and `p1`–`p4` at the start of
a word; `#` and `/` take the longest matching name, and an unmatched one stays
in the text. A backslash keeps a token as text. Unknown labels are created.

## API — `/api/v1/todos/`

`projects/`, `sections/`, `tasks/`, `labels/` (list, create, read, `PATCH`, `DELETE`, and
`POST …/reorder/` with the ordered list of sibling ids), `tasks/{id}/close/`,
`tasks/{id}/reopen/`, `tasks/quick/`, `filters/` and
`filters/{slug}/favourite/` (`POST` pins, `DELETE` unpins).

`tasks/` lists open tasks by default; it takes `?project=&section=&parent=`
(`none` for no section or the top level) `&label=&filter=&q=&completed=true`.
`sections/` takes `?project=&q=`. `q` searches
content and description, open tasks first. Lists aren't paginated: the limits
below bound them.

Everything is the caller's own; anyone else's rows are `404`.

## Settings

| Setting | Default |
| ------- | ------- |
| `TODOS_MAX_PROJECTS` | 500 per member |
| `TODOS_MAX_SECTIONS_PER_PROJECT` | 50 |
| `TODOS_MAX_TASKS_PER_PROJECT` | 5,000 open tasks |
| `TODOS_MAX_LABELS` | 500 per member |
| `TODOS_MAX_EXTRA_BYTES` | 16 KB |
| `TODOS_WRITE_RATE` | `1000/hour` per member, writes only |

Each reads `FINEXITO_<name>` from the environment.
