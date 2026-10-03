# PRD: Todos, phase 1 — Core

Status: **draft** · Owner: Amir Ehsandar · Last updated: 2026-10-03

Phase 1 of 4. Next: [phase 2, dates and reminders](2-dates-and-reminders.md),
[phase 3, collaboration](3-collaboration.md), then
[phase 4, templates, offline and Google Calendar](4-templates-offline-calendar.md).

## Summary

A `todos` app: a personal task manager with an Inbox, projects, sections, tasks
and sub-tasks, priorities, labels, built-in filters, search, and list and board
views, with one-line quick add. It is an optional facility like `content` and
`storage`: a deployment switches it on by adding it to `INSTALLED_APPS`, and
taking it out removes it cleanly.

There is no paid tier. Every member gets every feature; limits exist only to
protect the server from abuse.

## Goals

- Any product built on this base can offer a capable task manager without
  writing one.
- Capturing a task takes one line and a keystroke.
- A member can organise hundreds of tasks without the app getting in the way.

## Out of scope for this phase

- Due dates, recurrence, Today and Upcoming, reminders, email: phase 2.
- Sharing, assignees, comments, attachments: phase 3.

## Never in scope

- User-defined filters or a filter query language.
- Calendar or timeline views, task durations.
- Activity history, productivity stats, streaks.
- Integrations other than Google Calendar; email-to-task.

Templates, offline use and Google Calendar come in phase 4; until then the
client is online and refetches on focus.

## Concepts

| Concept     | Model     | Notes |
| ----------- | --------- | ----- |
| Inbox       | `Project` with `is_inbox` | One per member, created with the account. Can't be renamed, deleted, archived or nested. Where tasks go when no project is named. |
| Project     | `Project` | A named collection of tasks; projects nest. |
| Section     | `Section` | A heading inside one project. |
| Task        | `Task`    | A to-do in a project, optionally in a section, optionally under another task. |
| Label       | `Label`   | A member's own tag, usable across all their projects. |
| Filter      | code      | A predefined, read-only view over tasks (see [Filters](#filters)). |
| Favourite filter | `FavouriteFilter` | A member's pin of a filter slug, so it shows in the sidebar. |

### One model per level

Projects, sections and tasks are separate models, each with its own rules,
rather than one generic tree: each level is expected to grow behaviour of its
own.

Each task also has an `extra` JSON field for data the app doesn't model yet.
The app stores and returns it but never reads it.

## User stories

1. I press `q` anywhere (or the + button) and type one line to add a task; it
   lands in my Inbox unless I name a project.
2. Quick add understands `#Project` or `#label`, `/Section` and `p1`–`p4`, and
   shows them highlighted as I type so I can see what it understood. Typing `#`
   suggests matching projects first, then labels.
3. I create projects, give them a colour, nest them, favourite them and
   archive them when done.
4. I split a project into sections and move tasks between them.
5. I break a task into sub-tasks, and drag tasks to reorder them or to nest one
   under another.
6. I tick a task off and can undo it from the toast that appears.
7. I tag tasks with labels and open a label to see its tasks across projects.
8. I open a built-in filter, such as *Priority 1*, and pin it to the sidebar.
9. I search my tasks by text.
10. I switch a project between list and board view.

## Functional requirements

### Projects

| Field         | Notes |
| ------------- | ----- |
| `name`        | Required, up to 120 characters, trimmed. |
| `colour`      | One of the theme's named colours, not a hex value, so it follows the brand. Default: the neutral one. |
| `parent`      | Optional; nesting up to 3 levels. |
| `is_favourite`| Favourites also appear in a Favourites group at the top of the sidebar. |
| `is_archived` | Hidden from the sidebar and from every view, filter and search, with its sections and tasks. |
| `view`        | `list` / `board`, remembered per project. |
| `sort`        | `manual` / `priority` / `name` / `added`. Default `manual`. |
| `order`       | Position among its siblings in the sidebar. |

- Archiving a project archives its sub-projects; unarchiving restores them.
  Archived projects are listed under "Archived" in the projects page.
- Deleting asks for confirmation and deletes sub-projects, sections and tasks.
- Moving a project under another moves its sub-projects with it; a move that
  would exceed 3 levels is refused.

### Sections

| Field         | Notes |
| ------------- | ----- |
| `project`     | Required. |
| `name`        | Required, up to 500 characters. |
| `order`       | Position in the project. |
| `is_archived` | Hidden, with its tasks. |

### Tasks

| Field         | Notes |
| ------------- | ----- |
| `project`     | Required. |
| `section`     | Optional section in the same project. |
| `parent`      | Optional task; a sub-task shares its parent's project and section. |
| `order`       | Position among siblings (same project, section and parent). |
| `content`     | Required, up to 500 characters. Inline Markdown (bold, italic, code, links). |
| `description` | Optional Markdown, up to 16,000 characters. |
| `priority`    | `1` (most urgent, red) to `4` (none, default). Written `p1`–`p4`. Colours come from the theme. |
| `labels`      | Any of the member's labels. |
| `completed_at`| Set on completion, cleared on undo. |
| `extra`       | JSON object, up to 16 KB. Stored and returned as is. |

Tasks nest up to 4 levels.

**Sections**

- Tasks at the top level sit above the first section (the board shows them as
  "(No section)").
- A section can be renamed, reordered, moved to another project (with its
  tasks), archived or deleted (with its tasks, after confirmation).

**Tasks**

- **Sub-tasks** always live in their parent's project; moving the parent moves
  them. Dragging a task right under another nests it; dragging it left
  un-nests it. The parent shows a count like `2/5` and can be collapsed.
- **Completing** a task hides it from the list and shows an *Undo* toast for a
  few seconds. Completing a parent completes all its open sub-tasks. Completing
  a sub-task leaves the parent alone. Reopening a task reopens its parent if
  that was completed.
- **Completed tasks** can be shown per project ("Show completed"), newest first,
  and reopened from there.
- **Deleting** a task deletes its sub-tasks, after confirmation.
- **Ordering** is manual by default. The project's `sort` changes only how it
  is displayed, not the manual order.
- **Moving** a task between projects keeps its labels, sub-tasks and `extra`;
  it lands at the top level unless a section is chosen.

### Quick add

One line in, one task out. Parsing happens in the client, so it can highlight
what it understood and say what it will create (new labels, a new section)
before anything is saved. Saving uses the ordinary endpoints: the new labels and
section first, then the task. The API has no quick-add endpoint.

| Token            | Meaning |
| ---------------- | ------- |
| `#name`          | Project or label, matched case-insensitively on name; multi-word names match the longest existing one. A project wins over a label, and only the first project counts. No match: a label named after the next word is created. |
| `/Section`       | Section within the chosen project (or Inbox), matched the same way. No match: a section named after the next word is created. |
| `p1`–`p4`        | Priority. |

- Everything else is the task's content, with the tokens removed.
- `@` is reserved for mentioning people (collaboration) and stays plain text.
- A token can be escaped with a backslash to keep it as text.
- Opened from a project, section, task or label view, quick add pre-fills that
  project, parent or label.
- Phase 2 adds dates to this grammar.

### Labels

- A name (letters, digits, `_` and `-`, up to 60 characters, unique per member,
  case-insensitive), a colour from the theme, a favourite flag and an order.
- Renaming a label renames it everywhere; deleting it removes it from tasks,
  without deleting the tasks.
- A label's page lists its open tasks across all projects, grouped by project.

### Filters

Filters are code, not data. Each is a subclass of a `Filter` base with a slug,
a name and a `queryset(user)` method; adding a filter means adding a class.
Members can't create or edit them. They can favourite them, which stores a
`FavouriteFilter` row (member, slug, order) so they appear in the sidebar; a row
whose slug no longer exists is ignored.

Phase 1 set:

| Filter               | Shows |
| -------------------- | ----- |
| Priority 1           | Open `p1` tasks |
| Priority 2           | Open `p2` tasks |
| No labels            | Open tasks without a label |
| Recently completed   | Tasks completed in the last 7 days |

Phases 2 and 3 add date and assignee filters.

### Search

- Matches task content and description as a case-insensitive substring
  (`icontains`) across all non-archived projects. Results grouped by project,
  open tasks first.
- Also matches project, section and label names, shown above the tasks.
- No external search service. Full-text search can replace `icontains` if
  volume ever needs it.

### Views

- **Sidebar:** Inbox, Filters & Labels, Favourites, then My Projects as a tree.
- **List:** the project's tree, with sections as headings and tasks indented
  under their parents.
- **Board:** one column per section, with "(No section)" first; cards show
  content, priority colour, labels and the sub-task count. Dragging a card
  moves it between sections and reorders it. Sub-tasks don't get their own
  cards.

### Keyboard

| Key       | Action |
| --------- | ------ |
| `q`       | Quick add |
| `/`       | Search |
| `g` `i`   | Go to Inbox |
| `↑` `↓` / `j` `k` | Move between tasks |
| `e`       | Complete the selected task |
| `Enter`   | Open the selected task |
| `1`–`4`   | Set priority of the selected task |
| `#`       | Move the selected task to a project |
| `@`       | Edit labels of the selected task |
| `Delete`  | Delete the selected task |
| `?`       | Show these shortcuts |

### Limits

Only to stop one account from hurting the server. All are settings, set high
enough that real use never meets them; hitting one returns a clear error.

| Setting                       | Default |
| ----------------------------- | ------- |
| `TODOS_MAX_PROJECTS`          | 500 per member, archived included |
| `TODOS_MAX_SECTIONS_PER_PROJECT` | 50 |
| `TODOS_MAX_TASKS_PER_PROJECT` | 5,000 open tasks |
| `TODOS_MAX_LABELS`            | 500 per member |
| `TODOS_MAX_EXTRA_BYTES`       | 16 KB per task |
| `TODOS_WRITE_RATE`            | `1000/hour` per member |

Writes use DRF's `ScopedRateThrottle` with scope `todos`, rated by
`TODOS_WRITE_RATE`, so a script can't flood the database.

## API — `/api/v1/`

| Method          | Path                       | Purpose |
| --------------- | -------------------------- | ------- |
| GET, POST       | `todos/projects/`          | My projects, Inbox included. `?archived=` |
| GET, PATCH, DEL | `todos/projects/{id}/`     | Includes archive / unarchive and moving |
| GET, POST       | `todos/sections/`          | `?project=&q=` |
| GET, PATCH, DEL | `todos/sections/{id}/`     | Rename, move, archive |
| GET, POST       | `todos/tasks/`             | `?project=&section=&parent=&label=&filter=&q=&completed=` |
| GET, PATCH, DEL | `todos/tasks/{id}/`        | Edit, move, nest |
| POST            | `todos/tasks/{id}/close/`  | Complete (with sub-tasks) |
| POST            | `todos/tasks/{id}/reopen/` | Undo |
| GET, POST       | `todos/labels/`            | |
| PATCH, DEL      | `todos/labels/{id}/`       | |
| GET             | `todos/filters/`           | The built-in filters, with `is_favourite` |
| POST, DEL       | `todos/filters/{slug}/favourite/` | Pin or unpin a filter |
| POST            | `todos/{kind}/reorder/`    | `kind` is `projects`, `sections`, `tasks` or `labels`; body is the ordered list of sibling ids |

Every endpoint requires sign-in. Anything the caller can't see is `404`.

## Admin

Projects (owner, task count, archived; filters on archived and inbox; search by
name and owner email), sections (project, archived), tasks (project, section,
priority, completed; filters on priority and completion; search by content;
`extra` shown as formatted JSON), labels (owner, task
count). Read-only where code owns the data: completion times, the Inbox flag.

## Dependencies

`accounts`. On the frontend, the Markdown renderer, which moves out of
`content` into shared frontend code so `todos` works without `content`
installed. No new packages on the backend.

## Success measures

- Share of active members who add a task in their first week.
- Share of tasks created through quick add.
- Tasks completed per active member per week.

## Open questions

1. **Frontend:** do keyboard shortcuts and the board view ship in this phase,
   or straight after?
