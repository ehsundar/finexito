"use client";

import { Search } from "lucide-react";
import Form from "next/form";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useTodos } from "@/app/todos/shell";
import { TasksByProject } from "@/app/todos/tasks-by-project";
import { AppBar, Screen } from "@/components/app/frame";
import { Input } from "@/components/ui/input";
import { useQuery } from "@/lib/api/client";

export default function SearchPage() {
  const q = (useSearchParams().get("q") ?? "").trim();
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

function Results({ q }: { q: string }) {
  const { projects, labels } = useTodos();
  const { data: sections = [] } = useQuery("/api/v1/todos/sections/", { params: { query: { q } } });
  const { data: tasks } = useQuery("/api/v1/todos/tasks/", { params: { query: { q } } });
  const needle = q.toLowerCase();
  const names = [
    ...projects
      .filter((p) => p.name.toLowerCase().includes(needle))
      .map((p) => ({ key: p.id, text: p.name, href: p.is_inbox ? "/todos" : `/todos/project?id=${p.id}` })),
    ...sections.map((s) => ({
      key: s.id,
      text: `${projects.find((p) => p.id === s.project)?.name ?? ""} / ${s.name}`,
      href: `/todos/project?id=${s.project}`,
    })),
    ...labels
      .filter((l) => l.name.toLowerCase().includes(needle))
      .map((l) => ({ key: l.id, text: `#${l.name}`, href: `/todos/label?id=${l.id}` })),
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
      {tasks && <TasksByProject tasks={tasks} empty="No tasks match." />}
    </>
  );
}
