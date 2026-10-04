import { api, errorMessage, revalidate } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type Result<T = undefined> = { error?: string; data?: T };

/**
 * Every write the todos screens make. Django checks the session and ownership
 * on each call; these make it, then fetch what is on screen again.
 */
async function done<T>(call: Promise<{ data?: T; error?: unknown }>): Promise<Result<T>> {
  const { data, error } = await call;
  if (error) return { error: errorMessage(error) };
  revalidate();
  return { data };
}

const id = (value: string) => ({ params: { path: { id: value } } });

export async function createProject(body: Schemas["PatchedProjectRequest"] & { name: string }) {
  return done(api.POST("/api/v1/todos/projects/", { body }));
}

export async function updateProject(project: string, body: Schemas["PatchedProjectRequest"]) {
  return done(api.PATCH("/api/v1/todos/projects/{id}/", { ...id(project), body }));
}

export async function deleteProject(project: string) {
  return done(api.DELETE("/api/v1/todos/projects/{id}/", id(project)));
}

export async function createSection(project: string, name: string) {
  return done(api.POST("/api/v1/todos/sections/", { body: { project, name } }));
}

export async function updateSection(section: string, body: Schemas["PatchedSectionRequest"]) {
  return done(api.PATCH("/api/v1/todos/sections/{id}/", { ...id(section), body }));
}

export async function deleteSection(section: string) {
  return done(api.DELETE("/api/v1/todos/sections/{id}/", id(section)));
}

export async function createTask(body: Schemas["TaskRequest"]) {
  return done(api.POST("/api/v1/todos/tasks/", { body }));
}

export async function updateTask(task: string, body: Schemas["PatchedTaskRequest"]) {
  return done(api.PATCH("/api/v1/todos/tasks/{id}/", { ...id(task), body }));
}

export async function deleteTask(task: string) {
  return done(api.DELETE("/api/v1/todos/tasks/{id}/", id(task)));
}

export async function closeTask(task: string) {
  return done(api.POST("/api/v1/todos/tasks/{id}/close/", id(task)));
}

export async function reopenTask(task: string) {
  return done(api.POST("/api/v1/todos/tasks/{id}/reopen/", id(task)));
}

/** Moves a task (new section or parent), then puts its new siblings in order. */
export async function moveTask(task: string, body: Schemas["PatchedTaskRequest"], siblings: string[]) {
  const moved: { error?: unknown } = await api.PATCH("/api/v1/todos/tasks/{id}/", { ...id(task), body });
  if (moved.error) return { error: errorMessage(moved.error) };
  return done(api.POST("/api/v1/todos/tasks/reorder/", { body: siblings }));
}

export async function reorder(kind: "projects" | "sections" | "tasks" | "labels", ids: string[]) {
  const body = { body: ids };
  if (kind === "tasks") return done(api.POST("/api/v1/todos/tasks/reorder/", body));
  if (kind === "projects") return done(api.POST("/api/v1/todos/projects/reorder/", body));
  if (kind === "sections") return done(api.POST("/api/v1/todos/sections/reorder/", body));
  return done(api.POST("/api/v1/todos/labels/reorder/", body));
}

export async function createLabel(name: string) {
  return done(api.POST("/api/v1/todos/labels/", { body: { name } }));
}

export async function updateLabel(label: string, body: Schemas["PatchedLabelRequest"]) {
  return done(api.PATCH("/api/v1/todos/labels/{id}/", { ...id(label), body }));
}

export async function deleteLabel(label: string) {
  return done(api.DELETE("/api/v1/todos/labels/{id}/", id(label)));
}

export async function favouriteFilter(slug: string, on: boolean) {
  const path = { params: { path: { slug } } };
  return done(
    on
      ? api.POST("/api/v1/todos/filters/{slug}/favourite/", path)
      : api.DELETE("/api/v1/todos/filters/{slug}/favourite/", path),
  );
}

/** Moves tasks to a date, each keeping its time. */
export async function rescheduleTasks(tasks: string[], date: string) {
  return done(api.POST("/api/v1/todos/tasks/reschedule/", { body: { tasks, date } }));
}

/**
 * What a typed date means. With `find`, looks for one inside a task's text.
 * Called while typing, so it changes nothing and refetches nothing.
 */
export async function parseDue(text: string, find = false) {
  const { data, error } = await api.POST("/api/v1/todos/dates/parse/", { body: { text, find } });
  return error ? { error: errorMessage(error) } : { data };
}

export async function addReminder(task: string, body: Schemas["ReminderRequest"]) {
  return done(api.POST("/api/v1/todos/tasks/{id}/reminders/", { ...id(task), body }));
}

export async function deleteReminder(reminder: string) {
  return done(api.DELETE("/api/v1/todos/reminders/{id}/", id(reminder)));
}

/** Changes some keys of the profile's `extra`, keeping the others. */
export async function updateProfile(extra: Record<string, string>) {
  const { data } = await api.GET("/api/v1/profiles/me/");
  const body = { extra: { ...data?.extra, ...extra } };
  return done(api.PATCH("/api/v1/profiles/me/", { body }));
}

const path = (value: string) => ({ params: { path: { id: value } } });

/** Reads the project's invite link, makes a new one, or turns joining off. */
export async function inviteLink(project: string, change?: "reset" | "off") {
  if (change === "reset") return done(api.POST("/api/v1/todos/projects/{id}/invite-link/", path(project)));
  if (change === "off") return done(api.DELETE("/api/v1/todos/projects/{id}/invite-link/", path(project)));
  const { data, error } = await api.GET("/api/v1/todos/projects/{id}/invite-link/", path(project));
  return error ? { error: errorMessage(error) } : { data };
}

/** Removes someone from a project; with your own id, leaves it. */
export async function removeCollaborator(project: string, user: string) {
  return done(
    api.DELETE("/api/v1/todos/projects/{id}/collaborators/", {
      params: { path: { id: project }, query: { user } },
    }),
  );
}

export async function leaveProject(project: string) {
  const { data: me } = await api.GET("/api/v1/auth/me/");
  if (!me) return { error: "Couldn't reach the server." };
  return removeCollaborator(project, me.id);
}

export async function transferProject(project: string, user: string) {
  return done(api.POST("/api/v1/todos/projects/{id}/transfer/", { ...path(project), body: { user } }));
}

export async function joinProject(token: string) {
  return done(api.POST("/api/v1/todos/join/{token}/", { params: { path: { token } } }));
}

/** Uploads a file for a comment: a ticket first, then the bytes. Returns its id. */
export async function uploadAttachment(file: File): Promise<Result<string>> {
  const ticket = await api.POST("/api/v1/todos/comments/attachments/", {
    body: { name: file.name, content_type: file.type as Schemas["ContentTypeEnum"], size: file.size },
  });
  if (!ticket.data) return { error: errorMessage(ticket.error) };
  const sent = await api.PUT("/api/v1/storage/uploads/{id}/", {
    params: { path: { id: ticket.data.id } },
    body: file as unknown as string,
    bodySerializer: (body) => body,
    headers: { "Content-Type": file.type },
  });
  return sent.error ? { error: errorMessage(sent.error) } : { data: ticket.data.id };
}

export async function createComment(body: Schemas["CommentRequest"]) {
  return done(api.POST("/api/v1/todos/comments/", { body }));
}

export async function updateComment(comment: string, text: string) {
  return done(api.PATCH("/api/v1/todos/comments/{id}/", { ...path(comment), body: { text } }));
}

export async function deleteComment(comment: string) {
  return done(api.DELETE("/api/v1/todos/comments/{id}/", path(comment)));
}

export async function saveTemplate(project: string) {
  return done(api.POST("/api/v1/todos/templates/", { body: { project } }));
}

export async function importTemplate(file: File) {
  const form = new FormData();
  form.append("file", file);
  return done(
    api.POST("/api/v1/todos/templates/", {
      body: form as unknown as { file: string },
      bodySerializer: (body) => body as unknown as FormData,
    }),
  );
}

export async function applyTemplate(template: string, body: Schemas["ApplyTemplateRequest"] = {}) {
  return done(api.POST("/api/v1/todos/templates/{id}/apply/", { ...path(template), body }));
}

export async function renameTemplate(template: string, name: string) {
  return done(api.PATCH("/api/v1/todos/templates/{id}/", { ...path(template), body: { name } }));
}

export async function deleteTemplate(template: string) {
  return done(api.DELETE("/api/v1/todos/templates/{id}/", path(template)));
}

/** Downloads a template's or a project's CSV; the link needs the session, so it's fetched first. */
export async function downloadCsv(kind: "templates" | "projects", id: string) {
  const call =
    kind === "templates"
      ? api.GET("/api/v1/todos/templates/{id}/export/", { ...path(id), parseAs: "blob" })
      : api.GET("/api/v1/todos/projects/{id}/export/", { ...path(id), parseAs: "blob" });
  const { data, error, response } = await call;
  if (error || !data) return { error: errorMessage(error) };
  const name = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1];
  const link = document.createElement("a");
  link.href = URL.createObjectURL(data as Blob);
  link.download = name ?? "template.csv";
  link.click();
  URL.revokeObjectURL(link.href);
  return {};
}
