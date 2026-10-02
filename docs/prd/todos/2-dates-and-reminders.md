# PRD: Todos, phase 2 — Dates and reminders

Status: **draft** · Owner: Amir Ehsandar · Last updated: 2026-10-02

Phase 2 of 4. Builds on [phase 1, core](1-core.md); followed by
[phase 3, collaboration](3-collaboration.md).

## Summary

Due dates (with or without a time, one-off or recurring), typed in plain
English; the Today and Upcoming views; and reminders by email. Reminders come
from a new generic `reminders` app that knows nothing about tasks, so other
apps can use it later.

## Goals

- A member sees what to do today, and what's coming, across all projects.
- "every other Friday" is typed once and the task keeps coming back.
- A member is reminded in time without the app spamming them.

## Out of scope

- Location reminders, push or SMS notifications (email only for now).
- Deadlines separate from due dates, task durations, calendar view.
- Date parsing in languages other than English.

## User stories

1. I type `Pay rent every month on the 1st #Home p1` and get a recurring task.
2. I pick a date from a quick menu: Today, Tomorrow, This weekend, Next week,
   No date, or a calendar.
3. **Today** shows what's overdue and what's due today, across every project.
4. **Upcoming** shows the coming days, one heading per day, and I drag a task
   to another day to reschedule it.
5. I reschedule all overdue tasks to today in one click.
6. Completing a recurring task moves it to its next date.
7. I add reminders to a task and get an email when each one is due.
8. I choose whether timed tasks remind me by default, and how long before.

## Functional requirements

### Due dates

| Field       | Notes |
| ----------- | ----- |
| `due_date`  | Optional date. |
| `due_time`  | Optional; only with a date. Without it, the task is due "some time that day". |
| `due_string`| What the member typed (`every 2 weeks`), shown back to them. |
| `due_rule`  | The parsed RRULE, for recurring tasks. |
| `due_from_completion` | `every!` behaviour (see below). |

- Dates and times are in the member's time zone (from the profile). A timed
  task is stored as an instant, so it stays put if the member travels; a
  date-only task stays on its date in whatever zone they're in.
- A task is **overdue** once its date has passed (date-only) or its time has
  passed (timed). Overdue dates show in the theme's danger colour.
- Dates display relatively: *Today*, *Tomorrow*, the weekday within the next
  week, otherwise `12 Oct`, plus the year if it isn't this year.
- Sub-tasks have their own due dates, independent of the parent.

### Typing dates

Quick add and the date field accept English phrases. Recognised phrases are
highlighted and removed from the content; `\` escapes one.

| Typed                                 | Means |
| ------------------------------------- | ----- |
| `today`, `tod`, `tomorrow`, `tom`     | That day |
| `monday`, `mon`, `next friday`        | The next such day |
| `this weekend`, `next week`           | Saturday; next Monday |
| `in 3 days`, `in 2 weeks`             | Relative to today |
| `oct 12`, `12/10`, `12 october 2027`  | That date (day-first numbers, UK style) |
| `at 5pm`, `17:00`, `tomorrow 9am`     | Adds a time |
| `no date`                             | Clears it |
| `every day`, `daily`, `every weekday` | Recurring |
| `every monday`, `every mon, fri`      | Recurring on weekdays |
| `every 2 weeks`, `every other week`   | Interval |
| `every month on the 1st`, `every last day` | Monthly |
| `every year`, `every 12 oct`          | Yearly |
| `every day at 9am`                    | Recurring with a time |
| `every 3 days starting oct 6`, `... until dec 1`, `... for 5 times` | Start, end, count |
| `every!` …                            | Next date counts from completion, not from the due date |

- Parsing uses maintained packages (`dateparser` for one-off dates,
  `python-dateutil`'s rrule for recurrence) with a thin layer for the
  `every …` grammar; we don't write a date parser.
- A phrase that doesn't parse leaves the date unset and the text untouched; the
  date field shows "Couldn't understand that date".

### Recurrence

- Completing a recurring task doesn't close it: it records the completion and
  moves the due date to the next occurrence after the current due date, or,
  with `every!`, after today. Sub-tasks are reopened with it.
- A recurring task that has run out (`until`, `for N times`) closes normally on
  its last completion.
- Overdue recurring tasks advance to the next occurrence after **today**, so
  completing a daily task that's three days late doesn't leave it overdue.
- "Recently completed" lists each completion of a recurring task.
- Next-occurrence maths (time zones, DST, end of month) lives in the
  `reminders` app and is reused here, so there is one implementation.

### Today and Upcoming

- **Today:** an *Overdue* group (oldest first, with a "Reschedule" action that
  moves them all to today), then today's tasks: timed ones by time, then the
  rest by priority, then project.
- **Upcoming:** a week strip to jump between weeks, then one heading per day,
  starting with overdue. Dragging a task to another day changes its date and
  keeps its time. Each day has its own quick add, pre-filled with that date.
- The sidebar shows a count of today's tasks next to Today.

### New built-in filters

| Filter        | Shows |
| ------------- | ----- |
| Overdue       | Open tasks past their due date |
| Next 7 days   | Open tasks due within a week |
| No due date   | Open tasks without a date |
| Recurring     | Open recurring tasks |

### The `reminders` app

A new, generic app. It depends only on `accounts`, and knows nothing about
tasks.

- **Model.** A `Reminder` belongs to a user and points at any object (generic
  foreign key). It has a start instant, a time zone, an optional RRULE, and
  `next_at`, the next time it fires (empty once it's finished). One-off
  reminders have no RRULE.
- **Firing.** A management command, run by cron every minute, takes reminders
  whose `next_at` has passed (locking the rows, so overlapping runs can't fire
  one twice), fires each one, then moves `next_at` on or ends the reminder.
  Firing sends the `reminder_due` signal; the app that owns the target decides
  what to do with it.
- **Missed runs.** After downtime, each reminder fires once, not once per
  missed occurrence, and its next time is worked out from now.
- **Failures.** A failing receiver marks the reminder failed with the error,
  without stopping the others.
- **Admin.** Reminders by user, next time and status; filters on status and
  target type; actions to fire now and retry failed ones.
- **Deployment.** One cron entry in the existing Compose stack.

### Task reminders

- A task can have several reminders, each either **relative** to its due time
  ("30 minutes before", "1 day before") or at an **absolute** date and time.
  Relative ones need a timed due date.
- Each member has a default for timed tasks (off, at the time, or 10/30/60
  minutes before; default 30 minutes before), applied when a task gets a time.
  It can be removed per task.
- Changing the due date moves relative reminders. For a recurring task, they
  follow it to each new occurrence. Completing or deleting a task, or removing
  its date, ends its reminders.
- Firing sends an email through `apps.messaging` with the task, its project and
  a link to open it, using `SITE_NAME`. A reminder for a task that's already
  completed is skipped.
- A member can turn reminder emails off entirely in settings.

### Limits

| Setting                        | Default |
| ------------------------------ | ------- |
| `TODOS_MAX_REMINDERS_PER_TASK` | 10 |

Reminder emails are also capped per member per hour (`REMINDERS_MAX_PER_HOUR`,
default 60); beyond that they're deferred, not dropped.

## API — `/api/v1/` (additions)

| Method          | Path                          | Purpose |
| --------------- | ----------------------------- | ------- |
| GET             | `todos/items/?view=today`     | Overdue and today |
| GET             | `todos/items/?view=upcoming&from=&to=` | By day |
| POST            | `todos/items/reschedule/`     | Move many tasks to a date (e.g. all overdue) |
| POST            | `todos/dates/parse/`          | Parse a phrase, for the date field's preview |
| GET, POST       | `todos/items/{id}/reminders/` | A task's reminders |
| DEL             | `todos/reminders/{id}/`       | |

Task payloads gain the due fields; `close/` advances recurring tasks.

## Dependencies

`profiles` (time zone), `messaging` (email), the new `reminders` app. New
packages: `dateparser`, `python-dateutil`.

## Success measures

- Share of open tasks with a due date.
- Share of members who open Today at least three days a week.
- Reminder emails sent without failure; unsubscribe rate from them.

## Open questions

1. **Time zone:** is there one on the profile, or does this phase add it?
2. **Morning digest:** one email a day listing today's date-only tasks, or
   nothing for tasks without a time?
