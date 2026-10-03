import { Search } from "lucide-react";
import Form from "next/form";
import Link from "next/link";

import { TasksByProject } from "@/app/todos/tasks-by-project";
import { AppBar, Screen } from "@/components/app/frame";
import { Input } from "@/components/ui/input";
import { sessionApi } from "@/lib/auth/current-user";

export const metadata = { title: "Search" };

export default async function SearchPage({ searchParams }: PageProps<"/todos/search">) {
  const q = String((await searchParams).q ?? "").trim();
  return (
    <>
      <AppBar>
        <Form action="/todos/search" className="relative mr-2 flex-1">
          <Search className="text-muted-foreground absolute top-3 left-3 size-4" />
          <Input
            key={q}
            name="q"
            type="search"
            defaultValue={q}
            placeholder="Tasks, projects, labels"
            autoFocus={!q}
            className="h-10 rounded-full pl-9 text-base"
          />
        </Form>
      </AppBar>
      <Screen>{q && <Results q={q} />}</Screen>
    </>
  );
}

async function Results({ q }: { q: string }) {
  const api = await sessionApi();
  const [{ data: projects = [] }, { data: sections = [] }, { data: labels = [] }, { data: tasks = [] }] =
    await Promise.all([
      api.GET("/api/v1/todos/projects/"),
      api.GET("/api/v1/todos/sections/", { params: { query: { q } } }),
      api.GET("/api/v1/todos/labels/"),
      api.GET("/api/v1/todos/tasks/", { params: { query: { q } } }),
    ]);
  const needle = q.toLowerCase();
  const names = [
    ...projects
      .filter((p) => p.name.toLowerCase().includes(needle))
      .map((p) => ({ key: p.id, text: p.name, href: p.is_inbox ? "/todos" : `/todos/projects/${p.id}` })),
    ...sections.map((s) => ({
      key: s.id,
      text: `${projects.find((p) => p.id === s.project)?.name ?? ""} / ${s.name}`,
      href: `/todos/projects/${s.project}`,
    })),
    ...labels
      .filter((l) => l.name.toLowerCase().includes(needle))
      .map((l) => ({ key: l.id, text: `#${l.name}`, href: `/todos/labels/${l.id}` })),
  ];
  return (
    <>
      {names.length > 0 && (
        <ul className="-mx-4 flex gap-2 overflow-x-auto px-4">
          {names.map((n) => (
            <li key={n.key} className="shrink-0">
              <Link href={n.href} className="bg-secondary flex h-9 items-center rounded-full px-4 text-sm">
                {n.text}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <TasksByProject tasks={tasks} empty="No tasks match." />
    </>
  );
}
