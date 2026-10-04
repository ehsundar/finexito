# todos

A personal task manager: an Inbox, projects, sections, tasks and sub-tasks,
priorities, labels, built-in filters and search, with one-line quick add. The
specs are [docs/prd/todos/](../../../docs/prd/todos/).

It is several apps, each depending only on the ones above it:

| App | Label | What |
| --- | ----- | ---- |
| `apps.todos.projects` | `todos_projects` | Projects and sections, and the base the others build on (`TodosViewSet`, `CleanedSerializer`, the write throttle). |
| `apps.todos.tasks` | `todos_tasks` | Tasks, labels, filters, due dates and reminders. Needs `profiles` (time zone), `messaging` (reminder email) and `reminders`. |
| `apps.todos.comments` | `todos_comments` | Comments on tasks and projects, with attachments (`storage`) and notification emails. |
| `apps.todos.templates` | `todos_templates` | Built-in and saved templates, applying them, and CSV export and import. |
| `apps.todos.sync` | `todos_sync` | What offline clients need: changes since a token, deleted rows, and replaying queued calls. |
| `apps.todos.google` | `todos_google` | Dated tasks in the member's Google Calendar, and changes there back in the tasks. Leave it out where there's no Google API access. |

All are optional together: take them out of `INSTALLED_APPS` (and their
settings imports) and the todos are gone. Each also comes out on its own,
starting from the bottom of the table.

## Models

| Model            | What |
| ---------------- | ---- |
| `Project`        | A member's project; nests 3 levels. One per member is the Inbox (`is_inbox`), made the first time it is asked for (`Project.objects.inbox(user)`), and can't be renamed, archived, nested or deleted. |
| `ProjectMember`  | Someone a project is shared with, and their own place for it (parent, order, colour, favourite). |
| `Section`        | A heading inside one project. |
| `Task`           | In a project, optionally in one of its sections, optionally under another task; nests 4 levels. Optionally assigned to someone in the project. |
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
- `extra` is any JSON object up to `TODOS_TASKS_MAX_EXTRA_BYTES`, stored as is.

## Sharing

A project has an owner and collaborators, who join through its invite link
(`Project.invite_token`; blank turns joining off). Nothing is ever emailed to
someone who hasn't joined. The Inbox can't be shared, and sharing a project
doesn't share its sub-projects.

- Collaborators do everything with sections and tasks inside the project, but
  can't move them out, or rename, archive, delete or share the project. Changing
  its parent, colour or favourite changes only their own place for it.
- `Project.remove(user)` takes someone out (or lets them leave) and sends
  `member_left`; the tasks app unassigns them there and drops their reminders
  and labels on its tasks. `Project.transfer(user)` swaps the owner with a
  collaborator.
- Labels are each person's own: on a shared task, everyone sees and sets only
  theirs. Reminders are each person's too; a task getting a time gives the
  assignee their default reminder, or everyone if no one is assigned.
- `Task.tell_assignee(by)` emails someone given a task by someone else, unless
  their profile's `todos_assigned_emails` is `false`.

## Comments

`Comment` is on a task or a project (not both), in Markdown, with at most one
file. Files go through `apps.storage` as private objects: the client opens a
ticket (`comments/attachments/`), `PUT`s the file, then posts the comment with
`attachment_id`. Deleting a comment deletes its file; deleting a task or
project deletes its comments. `Task.comment_count` is kept by this app.

`Comment.notify()` emails, after a new comment, whoever created or is assigned
the task, or, for a project's own comments, everyone in it who set
`todos_project_comment_emails` to `true`; `todos_comment_emails` set to `false`
turns the first kind off. The author never hears about their own comment. An
email waits `TODOS_COMMENTS_EMAIL_DELAY_MINUTES`, and later comments on the same
thing join it until it goes.

## Templates

A template is a list of rows, the same as its CSV file's lines (`type`,
`content`, `description`, `priority`, `indent`, `labels`, `due`): a `section`
row starts a section, and a `task` indented one more than the task above is its
sub-task. `due` is an offset from the day it's applied (`+3`, `+3 09:00`) or a
recurrence phrase (`every monday`). `templates/models.py` has the format and
the three operations: `snapshot()` a project (open tasks, the member's own
labels; not comments, assignees or reminders), `apply()` rows to a new or
existing project (in one transaction, so a row breaking a limit creates
nothing; missing labels are made), and `to_csv()`/`from_csv()`.

Built-in templates are subclasses of `templates.builtin.BuiltIn`, like filters;
`TODOS_TEMPLATES_BUILT_IN` (comma-separated slugs) picks which a deployment
offers. A member's own are `Template` rows.

## Sync

For the offline client. `GET sync/?since=<token>` answers the projects,
sections, tasks and labels changed since the token (by `updated_at`, so bulk
`update()`s set it too), the rows deleted since (`Tombstone`s, kept
`TODOS_SYNC_TOMBSTONE_DAYS`), and a new token; no token, or one older than that,
answers everything with `full: true`. A project joined or re-placed since comes
whole. Tokens reach back a few seconds, so a change committed while a pull ran
isn't missed; rows sent twice just overwrite themselves.

`POST sync/` takes the calls the client queued offline, `{id, method, path,
body}`, and replays each through the API as the same member, in order, so every
rule and limit applies; it answers each one's status and body. A refused call
doesn't stop the rest, and an `id` already applied (`SyncOperation`) is skipped.
New rows may carry a client-made `id` (refused if taken), so queued calls can
refer to rows the server hasn't seen yet. Conflicts resolve by arrival: the last
`PATCH` of a field wins, and an edit after a delete is `404`.

## Google Calendar

`google/models.py`. Connecting asks Google for the narrowest scope that works
(`calendar.app.created`: only calendars the app makes) on top of sign-in, with
the same OAuth client; the Calendar API must be on in that Google Cloud project.
`Connection.connect()` keeps the refresh token encrypted
(`TODOS_GOOGLE_ENCRYPTION_KEY`), makes a calendar named "Tasks — `SITE_NAME`",
watches it, and sends the member's dated tasks: their own projects (or the ones
they chose) and shared projects' tasks assigned to them.

- A task is one event, whose id is the task's id in hex, so nothing links them
  but that. Timed tasks last `TODOS_GOOGLE_EVENT_MINUTES`; dated ones are
  all-day; a recurring one shows its next date. Completing, deleting or
  undating a task removes its event.
- Saving a task (and `tasks_changed`, for completing and reopening) notes a
  `Push` for each connection that might follow it, and a background task pushes
  them after the commit. A failed push waits, retried by the connection's
  reminder every 15 minutes (the reminders cron), which also renews the watch
  channel before it lapses.
- Google calls the webhook when the calendar changes; it checks the channel's
  token and a background task pulls the changes with the sync token. A moved or
  renamed event moves or renames its task; a deleted one takes its date away.
- A token Google refuses marks the connection disconnected. Disconnecting
  deletes the calendar, stops the channel and revokes the token.

## Due dates

A task has a `due_date`, in its owner's time zone (their profile's); a timed
one also has `due_at`, the instant, which is what counts for it, so it stays put
when the owner travels. The API reads and writes `due_date` and `due_time` in
the caller's zone.

`tasks/dates.py` reads English phrases (`tomorrow 9am`, `every other friday`,
`every! 3 days until dec 1`): `Due.parse()` a whole phrase, `Due.find()` one
inside a task's text. Calendar dates go to dateparser, recurrence to dateutil's
rrule; `due_rule` holds the DTSTART and RRULE.

- Closing a recurring task keeps it open and moves it to its next date: after
  its current one, or after today if it's overdue or `every!`. A completed copy
  (`completion_of`) records each completion, and its sub-tasks reopen.
  Reopening the task undoes its last completion. When the series runs out it
  closes like any task. The maths is `reminders.models.next_occurrence`.
- Reminders are `reminders.Reminder` rows pointing at the task: `minutes_before`
  its due time (kept in the reminder's `extra`, and moved with the due time) or
  at a fixed moment. A task that gets a time gets the owner's default reminder;
  losing its date drops them all. Firing emails the owner, unless the task is
  done or they've opted out.
- The member's preferences live in their profile's `extra`:
  `todos_reminder_before` (minutes, or `off`; default 30) and
  `todos_reminder_emails` (`false` turns the emails off).

Colours are names (`Colour`), not hex values; the frontend maps each to a
theme variable.

## Filters

`tasks/filters.py`. Each filter is a `Filter` subclass with a `slug`, a `name` and
`queryset(user)`; defining the class registers it.

## Quick add

The client parses the line (`#name`, `/Section`, `p1`–`p4`), so it can show
what it understood, and what it will create, before anything is saved. Then it
uses the plain endpoints: new labels and section first, then `POST tasks/`.
The rules live in `frontend/src/app/todos/quick-add.tsx`.

## API — `/api/v1/todos/`

`projects/`, `sections/`, `tasks/`, `labels/` (list, create, read, `PATCH`, `DELETE`, and
`POST …/reorder/` with the ordered list of sibling ids), `tasks/{id}/close/`,
`tasks/{id}/reopen/`, `tasks/reschedule/` (`{"tasks": [ids], "date": …}`, each
keeping its time), `tasks/{id}/reminders/` (`GET`, `POST`), `reminders/{id}/`
(`DELETE`), `dates/parse/` (`{"text": …, "find": true}` to look inside a task's
text), `filters/` and
`filters/{slug}/favourite/` (`POST` pins, `DELETE` unpins).

Sharing: `projects/{id}/collaborators/` (`GET` the owner then the rest;
`DELETE ?user=` removes someone, or leaves with your own id),
`projects/{id}/transfer/` (`{"user": …}`), `projects/{id}/invite-link/` (`GET`;
`POST` makes a new token; `DELETE` turns joining off), and `join/{token}/`
(`GET` a preview anyone holding the link may see; `POST` joins).

Templates: `templates/` (`GET` built-ins, whose ids are their slugs, then the
member's own; `POST {project}` saves one, `POST` a multipart `file` imports a
CSV), `templates/{id}/` (`PATCH`, `DELETE`: own only), `templates/{id}/apply/`
(`{project}` to add to one, else a new project, `{name}`), and
`templates/{id}/export/` and `projects/{id}/export/` (CSV).

Google Calendar: `google/` (`GET` status; `PATCH {projects}`, null for all;
`DELETE` disconnects), `google/connect/` (`GET` Google's consent URL),
`google/callback/` (`GET ?code=&state=` from the page Google returns to,
`/todos/google`), `google/webhook/` (Google's notices).

Sync: `sync/` (`GET ?since=`, `POST {operations}`).

Comments: `comments/` (`?task=` or `?project=`; `POST`, `PATCH` the text,
`DELETE`), `comments/attachments/` (`POST {name, content_type, size}` opens an
upload ticket).

`tasks/` lists open tasks by default; it takes `?project=&section=&parent=`
(`none` for no section or the top level) `&label=&filter=&q=&completed=true`,
or `?view=today` (overdue and today) or `?view=upcoming&from=&to=` (by day).
`sections/` takes `?project=&q=`. `q` searches
content and description, open tasks first. Lists aren't paginated: the limits
below bound them.

Everything is the caller's, or in a project they're in; anything else is `404`.

## Settings

| Setting | Default |
| ------- | ------- |
| `TODOS_PROJECTS_MAX` | 500 per member |
| `TODOS_PROJECTS_MAX_SECTIONS` | 50 |
| `TODOS_TASKS_MAX_PER_PROJECT` | 5,000 open tasks |
| `TODOS_TASKS_MAX_LABELS` | 500 per member |
| `TODOS_TASKS_MAX_EXTRA_BYTES` | 16 KB |
| `TODOS_PROJECTS_WRITE_RATE` | `1000/hour` per member, writes only |
| `TODOS_TASKS_MAX_REMINDERS` | 10 per member per task |
| `TODOS_PROJECTS_MAX_COLLABORATORS` | 50 |
| `TODOS_PROJECTS_JOIN_RATE` | `30/hour` per member or address |
| `TODOS_COMMENTS_MAX_ATTACHMENT_BYTES` | 25 MB |
| `TODOS_COMMENTS_MAX_STORAGE_BYTES` | 1 GB of attachments per member |
| `TODOS_COMMENTS_RATE` | `120/hour` new comments and uploads per member |
| `TODOS_COMMENTS_EMAIL_DELAY_MINUTES` | 5 |
| `TODOS_TEMPLATES_MAX` | 100 per member |
| `TODOS_TEMPLATES_MAX_TASKS` | 1,000 per template |
| `TODOS_TEMPLATES_BUILT_IN` | blank: all of them |
| `TODOS_SYNC_TOMBSTONE_DAYS` | 30 |
| `TODOS_SYNC_MAX_OPERATIONS` | 200 per `POST` |
| `TODOS_GOOGLE_EVENT_MINUTES` | 30 |
| `TODOS_GOOGLE_ENCRYPTION_KEY` | a Fernet key; a GitHub secret |

Each reads `FINEXITO_<name>` from the environment.

## Frontend

`frontend/src/app/todos/`: the screens, the writes in `actions.ts`, and the
keyboard shortcuts (press `?` in the app for the list).

Offline: `offline.ts` keeps a copy of the member's projects, sections, tasks and
labels in IndexedDB (Dexie), from `sync/`, and sits under the API client: when
the server can't be reached, todos reads are answered from the copy (running
the same list rules, filters included, as `tasks/`), other reads get the last
answer to the same URL, and writes to the copy, and comments, queue in an outbox
and apply locally. It syncs on opening, on focus, on reconnecting and every
minute; `connection.tsx` shows a line while offline or while changes wait. The
service worker (`frontend/worker/sw.ts`, built by `serwist build` after `next
build`) precaches the exported pages and caches scripts as they're used, and
offers "Update available" when a new version is deployed. A new built-in filter
needs its rule in `offline.ts` too. Date phrases typed offline stay in the
task's text; the server reads dates only online.
