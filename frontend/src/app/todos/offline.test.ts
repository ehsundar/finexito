import { describe, expect, it } from "vitest";

import { listTasks } from "@/app/todos/offline";
import type { Task } from "@/app/todos/shell";

const today = new Date().toLocaleDateString("en-CA");
const task = (fields: Partial<Task>) =>
  ({ order: 1, created_at: "2026-01-01", labels: [], priority: 4, completed_at: null, ...fields }) as Task;
const tasks = [
  task({ id: "a", content: "Buy milk", project: "home", due_date: today, priority: 1 }),
  task({ id: "b", content: "Old", project: "home", completed_at: "2026-01-02T00:00:00Z" }),
  task({ id: "c", content: "Sub", project: "home", parent: "a", order: 2 }),
  task({ id: "d", content: "Later", project: "work", due_date: "2999-01-01" }),
];
const list = async (query: string) =>
  ((await listTasks(tasks, new URLSearchParams(query))) as Task[]).map((t) => t.id);

describe("offline task lists", () => {
  it("lists open tasks, as the server does", async () => {
    expect(await list("project=home")).toEqual(["a", "c"]);
    expect(await list("project=home&parent=none")).toEqual(["a"]);
    expect(await list("completed=true")).toEqual(["b"]);
  });

  it("answers Today, filters and search", async () => {
    expect(await list("view=today")).toEqual(["a"]);
    expect(await list("filter=priority-1")).toEqual(["a"]);
    expect(await list("filter=no-due-date")).toEqual(["c"]);
    // Search finds completed tasks too, open ones first.
    expect(await list("q=l")).toEqual(["a", "d", "b"]);
  });
});
