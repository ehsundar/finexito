# PRD: Todos, phase 4 — Templates, offline and Google Calendar

Status: **draft** · Owner: Amir Ehsandar · Last updated: 2026-10-03

Phase 4 of 4. Builds on phases [1](1-core.md), [2](2-dates-and-reminders.md)
and [3](3-collaboration.md).

## Summary

Three independent pieces, each shippable on its own:

1. **Templates:** start a project from a ready-made structure, or save one of
   your own projects as a template.
2. **Offline and PWA:** install the app, use it with no connection, and have
   changes sync when it's back.
3. **Google Calendar:** dated tasks appear in the member's Google Calendar, and
   moving them there moves them here.

## Goals

- Recurring kinds of work (a trip, a launch, onboarding) start from a checklist
  instead of a blank project.
- The app is usable on a train: open it, add and tick off tasks, and nothing
  is lost.
- Members who live in their calendar see their tasks there.

## Out of scope

- A public template gallery, or sharing templates between members.
- Native mobile apps.
- Calendars other than Google; showing calendar events inside the app (see
  open questions).
- Offline sign-in, or offline attachments upload.

---

## 1. Templates

### User stories

1. When I create a project, I can pick a template instead of starting empty.
2. I save any of my projects as a template.
3. I apply a template to an existing project, adding its sections and tasks.

### Requirements

- A **template** is a snapshot of a project's structure: sections (in order),
  tasks and sub-tasks with content, description, priority, labels, order, and
  due dates as **offsets** from the day it's applied ("+3 days at 9:00") or as
  recurrence phrases ("every monday"). Not copied: completed tasks, comments,
  attachments, assignees, reminders other than the defaults.
- **Built-in templates** are code, like filters: each is a class with a slug,
  name, description, category and its content (a structure in Python or a
  bundled JSON file). Adding one is adding a class. The set is chosen per
  deployment by a setting, so a product shows only templates that suit it.
  Their text is written without product names; `SITE_NAME` where needed.
- **My templates** are stored per member: name, description, and the snapshot
  as JSON. Saving one from a project takes a snapshot; later edits to the
  project don't change it. A member can rename or delete their templates.
- **Applying** creates everything in one transaction. Labels the member doesn't
  have are created. As a new project, the template's name is the default
  project name. Into an existing project, its sections are added after the
  existing ones, and its unsectioned tasks after the existing unsectioned ones.
- Applying respects the [limits](1-core.md#limits); a template that would
  exceed one is refused before anything is created.
- **Export and import:** a template (or a project) can be downloaded as a CSV
  file in a documented format and uploaded again, by the same or another
  member. This also gives members a way to take their data with them.

### Limits

| Setting                      | Default |
| ---------------------------- | ------- |
| `TODOS_MAX_TEMPLATES`        | 100 per member |
| `TODOS_MAX_TEMPLATE_TASKS`   | 1,000 tasks per template |

### API

| Method          | Path                              | Purpose |
| --------------- | --------------------------------- | ------- |
| GET             | `todos/templates/`                | Built-in and mine |
| POST            | `todos/templates/`                | Save a project as a template (`project=`) or import a CSV |
| PATCH, DEL      | `todos/templates/{id}/`           | Mine only |
| POST            | `todos/templates/{id}/apply/`     | Into a new project, or `project=` |
| GET             | `todos/templates/{id}/export/`    | CSV |
| GET             | `todos/projects/{id}/export/`     | CSV |

---

## 2. Offline and PWA

### User stories

1. I install the app to my home screen or dock, and it opens like an app.
2. With no connection, I can open it, see my projects and tasks as last
   synced, and add, edit, complete, reorder and delete tasks.
3. When the connection returns, my changes upload and others' changes arrive,
   without me doing anything.
4. I can see when I'm offline and how many changes are waiting.

### Installable app

- A web app manifest: name and short name from `SITE_NAME`, icons and theme
  colours from the brand files (added to `brand/README.md`'s list), standalone
  display, start URL at the Inbox.
- A service worker, built with a maintained package (Serwist for Next.js),
  caches the app shell and static assets so the app opens offline.
- When a new version is deployed, the app offers "Update available — reload".

### Offline data

- The client keeps a copy of the member's projects, sections, tasks, labels and
  filters' inputs in IndexedDB (through a maintained wrapper such as Dexie), and
  reads from it first, so the app is fast online too.
- Comments and attachments are cached as read; offline, comments can be written
  (queued) but files can't be uploaded.
- Filters, Today and Upcoming run on the local copy when offline, so the same
  filter classes need a client-side equivalent. To keep one source of truth,
  each filter also declares its rule as simple data the client can evaluate
  (see open questions).
- Quick add already parses `#`, `/` and `p1`–`p4` on the client, so those work
  offline; date phrases are kept as typed and parsed by the server on sync.

### Sync

- **Client-made IDs.** Models already use UUID primary keys; the client creates
  them, so offline objects can be referenced (a task in a new project) before
  the server has seen them.
- **Outbox.** Every change offline is queued as an operation (create, update
  with the changed fields, delete, close, reopen, move). On reconnect, the
  queue is sent in order, in batches, to one endpoint. Each operation carries
  its own ID, so sending it twice does nothing the second time.
- **Pulling changes.** `GET todos/sync/?since=<token>` returns everything that
  changed (including deletions) since the token, and a new token. Deleted rows
  leave a tombstone for 30 days; a client older than that does a full reload.
- **Conflicts:** last write wins per field, using the server's order of
  arrival. Delete wins over edit. Completing a recurring task twice offline
  advances it once per completion. A rejected operation (no longer allowed, a
  limit hit, a project you were removed from) is dropped, and the member is
  shown what didn't sync.
- Online, the client syncs on focus, after each change, and every minute while
  open.

### API

| Method | Path                   | Purpose |
| ------ | ---------------------- | ------- |
| GET    | `todos/sync/?since=`   | Changes since a token; no token is a full load |
| POST   | `todos/sync/`          | Apply a batch of queued operations; returns per-operation results and a new token |

---

## 3. Google Calendar

A separate optional app (`todos_google`), so a deployment without Google API
access leaves it out. It depends on `todos` and `accounts`; `todos` never
imports it.

### User stories

1. In settings I connect my Google Calendar; I approve access once.
2. My dated tasks appear in a calendar of their own in Google Calendar.
3. Moving or renaming one of those events in Google Calendar updates the task.
4. Completing or deleting a task removes its event.
5. I disconnect, and the calendar is removed.

### Requirements

- **Consent.** Connecting asks for extra Google permission on top of sign-in
  (incremental authorisation), using the narrowest scope that works:
  `calendar.app.created`, which only allows managing calendars the app creates.
  The refresh token is stored encrypted. Sign-in itself doesn't change.
- **The calendar.** One secondary calendar per member, named after `SITE_NAME`
  ("Tasks — <site name>"), created on connect. The member chooses which
  projects to include (default: all, plus shared projects' tasks assigned to
  them).
- **Events.**
  - Timed task → event at its time, lasting `TODOS_GOOGLE_EVENT_MINUTES`
    (30).
  - Date-only task → all-day event.
  - Recurring task → one event for the next occurrence, moved forward when the
    task advances (not a recurring event, so it never shows occurrences the
    task will skip).
  - Title is the task's content; description has the project and a link back.
  - Completing, deleting, or removing the date removes the event.
- **Back from Google.** Changing an event's date, time or title updates the
  task; changing its duration doesn't. Deleting the event removes the task's
  date, not the task. Changes are picked up with Google's push notifications
  (watch channels) plus incremental sync tokens; channels expire after about a
  week and are renewed by a reminder from the `reminders` app.
- **Pushing to Google** happens after each task change commits, retried from a
  small outbox by the same cron command if Google is unreachable, so a slow
  Google never slows the app.
- **Disconnecting** deletes the calendar, stops the channel and revokes the
  token. Revoking access from Google's side is noticed on the next call and
  shown in settings as "Disconnected".
- **Admin.** Connections (member, status, last sync, last error) with an action
  to resync one.

### Settings

| Setting                          | Env var |
| -------------------------------- | ------- |
| `TODOS_GOOGLE_EVENT_MINUTES`     | `FINEXITO_TODOS_GOOGLE_EVENT_MINUTES` (default 30) |
| `TODOS_GOOGLE_ENCRYPTION_KEY`    | `FINEXITO_TODOS_GOOGLE_ENCRYPTION_KEY` (GitHub secret) |

The Google client ID and secret are the ones sign-in already uses; the Calendar
API must be enabled on that Google Cloud project, and the scope added to the
consent screen (which may need Google's verification).

### API

| Method    | Path                          | Purpose |
| --------- | ----------------------------- | ------- |
| GET, DEL  | `todos/google/`               | Connection status; disconnect |
| GET       | `todos/google/connect/`       | Start consent |
| GET       | `todos/google/callback/`      | Finish consent |
| PATCH     | `todos/google/`               | Which projects to include |
| POST      | `todos/google/webhook/`       | Google's push notifications (verified by channel token) |

Packages: `google-auth` and `google-api-python-client`.

---

## Success measures

- Projects created from a template, as a share of new projects.
- Share of active members who install the app.
- Offline operations that sync without being rejected.
- Share of members who connect Google Calendar, and who stay connected after a
  month.

## Open questions

1. **Filters offline:** declare each filter's rule as data (so the client and
   server evaluate the same thing), or keep filters online-only?
2. **Push notifications:** the PWA makes web push possible. Add it as a
   reminder channel next to email, here or later?
3. **Calendar events in the app:** show the member's Google Calendar events
   (read-only) in Today and Upcoming? That needs a wider, read-only scope on
   all their calendars.
4. **Built-in templates:** which ones ship by default?
