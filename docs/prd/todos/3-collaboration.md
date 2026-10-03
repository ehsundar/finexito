# PRD: Todos, phase 3 — Collaboration

Status: **draft** · Owner: Amir Ehsandar · Last updated: 2026-10-02

Phase 3 of 4. Builds on [phase 1](1-core.md) and
[phase 2](2-dates-and-reminders.md).

## Summary

Shared projects, joined through an invite link; assigning tasks; comments on
tasks and projects, with file attachments; and email notifications about them.

## Goals

- A household or a small team works from one project.
- Discussion and files about a task stay on the task.
- Our outgoing mail never goes to people who haven't joined.

## Out of scope

- Teams or workspaces, roles beyond owner and collaborator.
- Inviting by email (see [Sharing](#sharing)).
- Real-time updates; clients refetch on focus.
- Mentions, reactions, an activity log.

## User stories

1. I copy a project's invite link and send it to someone however I like.
2. Opening the link, they sign in (or sign up) and land in the project.
3. I see who's in a project, remove someone, or leave a project I joined.
4. I assign a task to someone in the project, and they're told. Typing `@name` in quick add or a comment mentions them; `@` is reserved for this from phase 1.
5. I comment on a task or a project, with Markdown and an attached file.
6. I'm emailed about tasks assigned to me and comments on tasks I'm involved in.

## Functional requirements

### Sharing

- **Invite links, no invitation email.** Emailing invitations would make our
  outgoing mail a spam channel, so the app never emails anyone who isn't a
  member of the project. The share dialog shows the project's link with a
  *Copy link* button and the line "Copy this link and send it to the people
  you want to invite."
- Opening the link: a signed-out visitor sees the project's name and who
  invited them, signs in with Google (creating an account if needed) and lands
  in the project. A signed-in visitor joins in one click.
- The owner can **reset** the link, which stops the old one working, or turn
  link joining off. The link stops working when the project is full.
- The Inbox can't be shared. Sharing a project doesn't share its sub-projects;
  each is shared on its own.
- **Roles:** the owner can do everything. Collaborators can add, edit,
  complete, move within the project and delete tasks, manage sections and
  comment; they can't rename, archive, delete or share the project, or remove
  people. Anyone except the owner can leave. The owner can hand ownership to
  a collaborator.
- Each collaborator keeps their own place for the project in their sidebar
  (order, nesting under their own projects, favourite, colour).
- A collaborator's labels are their own: on a shared task, each person sees
  and edits only their labels.
- Removing someone (or them leaving) unassigns their tasks there and ends their
  reminders for those tasks.
- Shared projects show the members' avatars in the header.

### Assignees

- A task in a shared project can be assigned to one member of that project.
  The avatar shows on the task; sub-tasks can be assigned separately.
- Assigning someone else sends them an email (they're a member, so this isn't
  mail to strangers). Assigning yourself sends nothing.
- On a shared project, the default reminder for a timed task goes to the
  assignee, or to everyone if it's unassigned.
- New built-in filters: *Assigned to me*, *Assigned to others*.

### Comments

- On a task or on a project. Markdown, up to 15,000 characters, rendered by the
  existing renderer. Shown oldest first, with author, avatar and time.
- The author can edit (marked "edited") or delete their own comment; the
  project owner can delete any.
- Tasks show a comment count. Comments also work on personal projects, as
  notes.
- Deleting a task or project deletes its comments.

### Attachments

- One file per comment, through `apps.storage`: the client asks for an upload
  ticket, sends the file, then posts the comment with it. Images show a preview;
  other files show their name, type and size.
- Files are private (signed links), visible to everyone who can see the
  project. Deleting the comment deletes the file.

### Notifications

- Email, through `apps.messaging`, using `SITE_NAME`:
  - a task is assigned to you;
  - someone comments on a task you created or are assigned to, or on a project
    you're in (project comments only if you opt in).
- Never sent for your own actions, never to non-members.
- Bursts are grouped: comments on the same task within a few minutes go out as
  one email.
- Each kind can be turned off in settings.

### Limits

| Setting                           | Default |
| --------------------------------- | ------- |
| `TODOS_MAX_PROJECT_COLLABORATORS` | 50 |
| `TODOS_MAX_ATTACHMENT_BYTES`      | 25 MB |
| `TODOS_MAX_STORAGE_BYTES`         | 1 GB of attachments per member |

Comment creation and joining are throttled, so a script can't flood a project
or trigger a storm of emails.

## API — `/api/v1/` (additions)

| Method          | Path                                    | Purpose |
| --------------- | --------------------------------------- | ------- |
| GET, DEL        | `todos/projects/{id}/collaborators/`    | List; remove (or leave, with your own id) |
| POST            | `todos/projects/{id}/transfer/`         | Hand ownership to a collaborator |
| GET, POST, DEL  | `todos/projects/{id}/invite-link/`      | Read; reset; turn off |
| GET, POST       | `todos/join/{token}/`                   | Preview; join |
| GET, POST       | `todos/comments/`                       | `?task=` or `?project=` |
| PATCH, DEL      | `todos/comments/{id}/`                  | |
| POST            | `todos/comments/attachments/`           | Open an upload ticket |

Task payloads gain `assignee`. Anything the caller can't see is `404`.

## Admin

Project members inline on projects (read-only); comments (author, task or
project, has attachment; search by text). Action: resend a failed notification.

## Dependencies

`storage` (attachments), `messaging` (email), `accounts` (Google sign-in
redirecting back to the invite link).

## Success measures

- Share of projects with a collaborator.
- Share of invite links that lead to a join.
- Comments per shared project per week.

## Open questions

1. Should the signed-out invite page show the project's name, or is that too
   much for anyone holding a leaked link?
