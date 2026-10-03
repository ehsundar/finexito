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
