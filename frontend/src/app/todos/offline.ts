/**
 * The todos client offline: a copy of the member's projects, sections, tasks and
 * labels in IndexedDB (through Dexie), kept fresh from `todos/sync/`, and an
 * outbox of the writes made while the server can't be reached.
 *
 * It sits under the API client (`handleOffline` in lib/api/client.ts), so the
 * screens don't change: when a todos call can't reach the server, a read is
 * answered from the copy and a write is queued, applied to the copy, and
 * answered as the server would have. On reconnecting, the outbox goes to
 * `POST todos/sync/` in order and the changes since come back.
 *
 * Reads the copy can't answer (filters' list, comments, people) get the last
 * answer the server gave to the same URL.
 */

import Dexie, { type Table } from "dexie";
import { toast } from "sonner";

import { api, revalidate } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
type Project = Schemas["Project"];
type Section = Schemas["Section"];
type Task = Schemas["Task"];
type Label = Schemas["Label"];
type Op = { seq?: number; id: string; method: "POST" | "PATCH" | "DELETE"; path: string; body: unknown };
type Json = Record<string, unknown>;

class Store extends Dexie {
  projects!: Table<Project, string>;
  sections!: Table<Section, string>;
  tasks!: Table<Task, string>;
  labels!: Table<Label, string>;
  outbox!: Table<Op, number>;
  responses!: Table<{ url: string; body: string }, string>;
  meta!: Table<{ key: string; value: string }, string>;

  constructor() {
    super("todos");
    this.version(1).stores({
      projects: "id",
      sections: "id, project",
      tasks: "id, project",
      labels: "id",
      outbox: "++seq",
      responses: "url",
      meta: "key",
    });
  }
}

const db = new Store();
const TODOS = "/api/v1/todos/";

// --- what the screens see: online or not, and how much is waiting ---------------

type State = { online: boolean; waiting: number };
let state: State = { online: true, waiting: 0 };
const listeners = new Set<() => void>();

function setState(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((listener) => listener());
}

export const syncState = {
  subscribe: (listener: () => void) => (listeners.add(listener), () => listeners.delete(listener)),
  get: () => state,
  server: () => state,
};

async function countWaiting() {
  setState({ waiting: await db.outbox.count() });
}

// --- the handler under the API client ------------------------------------------

/** Answers a todos call from the server, or, when it can't be reached, from here. */
export async function offlineFetch(request: Request, network: (request: Request) => Promise<Response>) {
  const url = new URL(request.url);
  if (!url.pathname.startsWith(TODOS) || url.pathname.startsWith(`${TODOS}sync/`)) return network(request);
  const key = url.pathname + url.search;

  if (request.method === "GET") {
    try {
      const response = await network(request);
      setState({ online: true });
      if (response.ok) void db.responses.put({ url: key, body: await response.clone().text() });
      return response;
    } catch {
      setState({ online: false });
      return answer(url);
    }
  }

  // Writes keep their order: while anything waits, new ones queue behind it.
  // JSON, or nothing (close, reopen); a form (a file) can't wait.
  const type = request.headers.get("Content-Type");
  const isJson = !type || type.includes("json");
  const text = await request.clone().text();
  const body = isJson && text ? JSON.parse(text) : {};
  if (!(await db.outbox.count())) {
    try {
      const response = await network(request);
      setState({ online: true });
      return response;
    } catch {
      setState({ online: false });
    }
  }
  // Only changes to the copy, and comments, wait for the connection; the rest
  // (dates read on the server, templates, sharing, files) need it now.
  const [kind, id] = parts(url);
  const queues = kind in TABLES || (kind === "comments" && id !== "attachments");
  if (!queues || !isJson) return failure("You're offline; try again when you're back.");
  return queue(request.method as Op["method"], url, body);
}

/** Queues a write and applies it to the local copy, answering as the server would. */
async function queue(method: Op["method"], url: URL, body: Json) {
  const [kind, id, action] = parts(url);
  if (method === "POST" && !id && !body.id) body = { ...body, id: crypto.randomUUID() };
  await db.outbox.add({ id: crypto.randomUUID(), method, path: url.pathname + url.search, body });
  void countWaiting();
  const result = await applyLocally(method, kind, id, action, body);
  revalidate();
  return result;
}

const parts = (url: URL) => url.pathname.slice(TODOS.length).split("/").filter(Boolean);

const json = (data: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const failure = (message: string) =>
  json({ error: { code: "offline", message, fields: {} } }, 503);

const now = () => new Date().toISOString();
const today = () => new Date().toLocaleDateString("en-CA");
const addDays = (day: string, days: number) => {
  const date = new Date(`${day}T12:00`);
  date.setDate(date.getDate() + days);
  return date.toLocaleDateString("en-CA");
};

// --- reading the copy ----------------------------------------------------------

async function answer(url: URL): Promise<Response> {
  const [kind, id, action] = parts(url);
  const params = url.searchParams;
  if (!action && kind === "projects") {
    const projects = await withCounts(await db.projects.toArray());
    if (id) return found(projects.find((p) => p.id === id));
    const archived = params.get("archived") === "true";
    return json(projects.filter((p) => !!p.is_archived === archived).sort(byOrder));
  }
  if (!action && kind === "sections") {
    if (id) return found(await db.sections.get(id));
    const archivedProjects = new Set((await db.projects.toArray()).filter((p) => p.is_archived).map((p) => p.id));
    let sections = (await db.sections.toArray()).filter((s) => !s.is_archived && !archivedProjects.has(s.project));
    if (params.get("project")) sections = sections.filter((s) => s.project === params.get("project"));
    if (params.get("q")) sections = sections.filter((s) => s.name.toLowerCase().includes(params.get("q")!.toLowerCase()));
    return json(sections.sort(byOrder));
  }
  if (!action && kind === "labels") {
    const tasks = await visibleTasks();
    const labels = (await db.labels.toArray()).map((l) => ({
      ...l,
      open_task_count: tasks.filter((t) => !t.completed_at && t.labels?.includes(l.id)).length,
    }));
    return id ? found(labels.find((l) => l.id === id)) : json(labels.sort(byOrder));
  }
  if (!action && kind === "tasks" && id !== "reschedule") {
    const all = await visibleTasks();
    if (id) return found(all.find((t) => t.id === id));
    const listed = await listTasks(all, params, (await db.meta.get("user"))?.value);
    return listed instanceof Response ? listed : json(listed);
  }
  const cached = await db.responses.get(url.pathname + url.search);
  return cached ? new Response(cached.body, { headers: { "Content-Type": "application/json" } }) : failure("You're offline.");
}

const found = (row: unknown) => (row ? json(row) : json({ error: { code: "not_found", message: "Not found.", fields: {} } }, 404));
const byOrder = (a: { order: number }, b: { order: number }) => a.order - b.order;

async function withCounts(projects: Project[]) {
  const tasks = await visibleTasks();
  return projects.map((p) => ({
    ...p,
    open_task_count: tasks.filter((t) => t.project === p.id && !t.completed_at).length,
  }));
}

/** Tasks as the server lists them: not in archived projects or sections, with their counts. */
async function visibleTasks(): Promise<Task[]> {
  const hidden = new Set([
    ...(await db.projects.toArray()).filter((p) => p.is_archived).map((p) => p.id),
    ...(await db.sections.toArray()).filter((s) => s.is_archived).map((s) => s.id),
  ]);
  const tasks = await db.tasks.toArray();
  const stamp = today();
  return tasks
    .filter((t) => !hidden.has(t.project) && !(t.section && hidden.has(t.section)))
    .map((t) => {
      const children = tasks.filter((c) => c.parent === t.id);
      return {
        ...t,
        subtask_count: children.length,
        completed_subtask_count: children.filter((c) => c.completed_at).length,
        is_overdue: !t.completed_at && !!t.due_date && due(t) < (t.due_time ? new Date() : new Date(`${stamp}T00:00`)),
      };
    });
}

const due = (t: Task) => new Date(`${t.due_date}T${t.due_time ?? "00:00"}`);
const isOpen = (t: Task) => !t.completed_at;
const byDue = (a: Task, b: Task) =>
  (a.due_date ?? "").localeCompare(b.due_date ?? "") ||
  (a.due_time ?? "99").localeCompare(b.due_time ?? "99") ||
  (a.priority ?? 4) - (b.priority ?? 4) ||
  a.order - b.order;

/**
 * The built-in filters, as the server's (apps/todos/tasks/filters.py). A new
 * filter there needs its rule here too, or it shows nothing offline.
 */
const FILTERS: Record<string, (tasks: Task[], me: string) => Task[]> = {
  "priority-1": (tasks) => tasks.filter((t) => isOpen(t) && t.priority === 1),
  "priority-2": (tasks) => tasks.filter((t) => isOpen(t) && t.priority === 2),
  "no-labels": (tasks) => tasks.filter((t) => isOpen(t) && !t.labels?.length),
  "recently-completed": (tasks) => {
    const since = new Date(Date.now() - 7 * 864e5).toISOString();
    return tasks.filter((t) => t.completed_at && t.completed_at >= since).sort((a, b) => b.completed_at!.localeCompare(a.completed_at!));
  },
  overdue: (tasks) => tasks.filter((t) => isOpen(t) && t.is_overdue).sort(byDue),
  "next-7-days": (tasks) => {
    const [from, to] = [today(), addDays(today(), 7)];
    return tasks.filter((t) => isOpen(t) && t.due_date && t.due_date >= from && t.due_date < to).sort(byDue);
  },
  "no-due-date": (tasks) => tasks.filter((t) => isOpen(t) && !t.due_date),
  recurring: (tasks) => tasks.filter((t) => isOpen(t) && t.is_recurring).sort(byDue),
  "assigned-to-me": (tasks, me) => tasks.filter((t) => isOpen(t) && t.assignee === me),
  "assigned-to-others": (tasks, me) => tasks.filter((t) => isOpen(t) && t.assignee && t.assignee !== me),
};

/** `GET tasks/`, as the server answers it (apps/todos/tasks/views.py). */
export async function listTasks(all: Task[], params: URLSearchParams, me = ""): Promise<Task[] | Response> {
  let tasks = [...all].sort((a, b) => a.order - b.order || a.created_at.localeCompare(b.created_at));
  const q = params.get("q")?.toLowerCase();
  if (params.get("filter")) {
    const rule = FILTERS[params.get("filter")!];
    if (!rule) return found(null);
    tasks = rule(tasks, me);
  } else if (params.get("view") === "today") {
    tasks = tasks.filter((t) => isOpen(t) && t.due_date && t.due_date <= today()).sort(byDue);
  } else if (params.get("view") === "upcoming") {
    const from = params.get("from") ?? today();
    const to = params.get("to") ?? addDays(from, 6);
    tasks = tasks.filter((t) => isOpen(t) && t.due_date && t.due_date >= from && t.due_date <= to).sort(byDue);
  } else if (params.get("completed") === "true") {
    tasks = tasks.filter((t) => t.completed_at).sort((a, b) => b.completed_at!.localeCompare(a.completed_at!));
  } else if (!q) {
    tasks = tasks.filter(isOpen);
  }
  for (const name of ["project", "section", "parent"] as const) {
    const value = params.get(name);
    if (value) tasks = tasks.filter((t) => (t[name] ?? null) === (value === "none" ? null : value));
  }
  if (params.get("label")) tasks = tasks.filter((t) => t.labels?.includes(params.get("label")!));
  if (q) {
    tasks = tasks
      .filter((t) => t.content.toLowerCase().includes(q) || t.description?.toLowerCase().includes(q))
      .sort((a, b) => Number(!!a.completed_at) - Number(!!b.completed_at) || a.order - b.order);
  }
  return tasks;
}

// --- writing to the copy ---------------------------------------------------------

const TABLES = { projects: db.projects, sections: db.sections, tasks: db.tasks, labels: db.labels } as const;
type Kind = keyof typeof TABLES;

async function nextOrder(kind: Kind, siblings: (row: Json) => boolean) {
  const rows = (await TABLES[kind].toArray()) as unknown as (Json & { order: number })[];
  return Math.max(0, ...rows.filter(siblings).map((r) => r.order)) + 1;
}

/** What a new row looks like before the server has seen it. */
async function fresh(kind: Kind, body: Json): Promise<Json> {
  const me = (await db.meta.get("user"))?.value ?? null;
  const base = { created_at: now() };
  if (kind === "projects")
    return {
      ...base, colour: "neutral", parent: null, is_inbox: false, is_favourite: false, is_archived: false,
      view: "list", sort: "manual", is_owner: true, is_shared: false, open_task_count: 0, ...body,
      order: await nextOrder(kind, (r) => (r.parent ?? null) === (body.parent ?? null)),
    };
  if (kind === "sections")
    return { ...base, is_archived: false, ...body, order: await nextOrder(kind, (r) => r.project === body.project) };
  if (kind === "labels")
    return { colour: "neutral", is_favourite: false, open_task_count: 0, ...body, order: await nextOrder(kind, () => true) };
  return {
    ...base, updated_at: now(), section: null, parent: null, description: "", priority: 4, labels: [],
    assignee: null, created_by: me, comment_count: 0, completed_at: null, due_date: null, due_time: null,
    due_string: "", is_recurring: false, due_from_completion: false, is_overdue: false, extra: {},
    subtask_count: 0, completed_subtask_count: 0, ...body,
    order: await nextOrder(kind, (r) => r.project === body.project && (r.section ?? null) === (body.section ?? null) && (r.parent ?? null) === (body.parent ?? null)),
  };
}

async function descendants(id: string): Promise<string[]> {
  const tasks = await db.tasks.toArray();
  const ids: string[] = [];
  let level = [id];
  while (level.length) {
    level = tasks.filter((t) => t.parent && level.includes(t.parent)).map((t) => t.id);
    ids.push(...level);
  }
  return ids;
}

async function applyLocally(method: Op["method"], kind: string, id: string | undefined, action: string | undefined, body: Json): Promise<Response> {
  if (!(kind in TABLES)) return json({}, 202); // comments and the like: queued, shown once synced
  const table = TABLES[kind as Kind] as unknown as Table<Json, string>;
  if (method === "POST" && !id) {
    const row = await fresh(kind as Kind, body);
    await table.put(row);
    return json(row, 201);
  }
  if (method === "POST" && id === "reorder") {
    const ids = body as unknown as string[];
    await Promise.all(ids.map((pk, index) => table.update(pk, { order: index + 1 })));
    return json(null, 204);
  }
  if (method === "POST" && id === "reschedule") {
    const { tasks, date } = body as { tasks: string[]; date: string };
    await Promise.all(tasks.map((pk) => db.tasks.update(pk, { due_date: date })));
    return json(null, 204);
  }
  if (!id) return json({}, 202);
  if (method === "DELETE") {
    if (kind === "projects") {
      await db.tasks.where("project").equals(id).delete();
      await db.sections.where("project").equals(id).delete();
    }
    if (kind === "sections") await db.tasks.filter((t) => t.section === id).delete();
    if (kind === "tasks") await db.tasks.bulkDelete(await descendants(id));
    await table.delete(id);
    return json(null, 204);
  }
  if (kind === "tasks" && (action === "close" || action === "reopen")) {
    const completed_at = action === "close" ? now() : null;
    const ids = [id, ...(await descendants(id))];
    await Promise.all(ids.map((pk) => db.tasks.update(pk, { completed_at })));
  } else if (method === "PATCH") {
    await table.update(id, { ...body, updated_at: now() });
  } else {
    return json({}, 202);
  }
  return found(await table.get(id));
}

// --- talking to the server --------------------------------------------------------

let running: Promise<void> | null = null;

/** Sends what's queued, then takes in what changed; one run at a time. */
export function sync() {
  running ??= (async () => {
    try {
      if (await push()) await pull();
    } finally {
      running = null;
    }
  })();
  return running;
}

async function push(): Promise<boolean> {
  for (;;) {
    const batch = await db.outbox.orderBy("seq").limit(100).toArray();
    if (!batch.length) return true;
    let result;
    try {
      result = await api.POST("/api/v1/todos/sync/", {
        body: { operations: batch.map(({ id, method, path, body }) => ({ id, method, path, body })) },
      });
    } catch {
      setState({ online: false });
      return false;
    }
    if (!result.data) return false;
    setState({ online: true });
    const refused = result.data.filter((r) => r.status >= 400);
    if (refused.length) {
      const reason = (refused[0].body as { error?: { message?: string } } | null)?.error?.message;
      toast.error(
        `${refused.length} change${refused.length > 1 ? "s" : ""} made offline didn't sync${reason ? `: ${reason}` : "."}`,
      );
    }
    await db.outbox.bulkDelete(batch.map((op) => op.seq!));
    void countWaiting();
  }
}

async function pull() {
  try {
    await receive();
  } catch {
    setState({ online: false });
  }
}

async function receive() {
  const user = (await db.meta.get("user"))?.value;
  const { data: me } = await api.GET("/api/v1/auth/me/");
  if (!me) return;
  // Someone else signed in on this device: their copy, not the last person's.
  if (user && user !== me.id) await clear();
  await db.meta.put({ key: "user", value: me.id });

  const since = (await db.meta.get("token"))?.value;
  const { data } = await api.GET("/api/v1/todos/sync/", { params: { query: since ? { since } : {} } });
  if (!data) return;
  await db.transaction("rw", [db.projects, db.sections, db.tasks, db.labels, db.meta], async () => {
    if (data.full) await Promise.all([db.projects, db.sections, db.tasks, db.labels].map((t) => t.clear()));
    await db.projects.bulkPut(data.projects);
    await db.sections.bulkPut(data.sections);
    await db.tasks.bulkPut(data.tasks);
    await db.labels.bulkPut(data.labels);
    for (const { kind, id } of data.deleted) {
      if (kind === "project") {
        await db.tasks.where("project").equals(id).delete();
        await db.sections.where("project").equals(id).delete();
      }
      await TABLES[`${kind}s` as Kind].delete(id);
    }
    await db.meta.put({ key: "token", value: data.token });
  });
  revalidate();
}

/** Forgets everything, as at signing out. */
export async function clear() {
  await Promise.all(db.tables.map((table) => table.clear()));
  void countWaiting();
}

export async function start() {
  await countWaiting();
  await sync();
}
