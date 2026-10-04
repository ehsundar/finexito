"use client";

import { Archive, Filter, Hash, Inbox, LayoutTemplate, Search, Star, Users } from "lucide-react";
import Form from "next/form";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { colourVar, Dot, NewProject, useTodos, type Project } from "@/app/todos/shell";
import { TasksByProject } from "@/app/todos/tasks-by-project";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";
import { Input } from "@/components/ui/input";
import { useQuery } from "@/lib/api/client";

/** Search, and everything to open: favourites, projects (as a tree), filters and labels. */
export default function BrowsePage() {
  const q = (useSearchParams().get("q") ?? "").trim();
  return (
    <>
      <AppBar>
        <Form action="/todos/browse" className="relative mr-2 flex-1">
          <Search className="text-muted-foreground absolute top-3 left-3 size-4" />
          <Input
            key={q}
            name="q"
            type="search"
            defaultValue={q}
            placeholder="Search tasks, projects, labels"
            className="h-10 rounded-full pl-9 text-base"
          />
        </Form>
      </AppBar>
      <Screen>{q ? <Results q={q} /> : <Everything />}</Screen>
    </>
  );
}

function Everything() {
  const { projects, labels, filters } = useTodos();
  const { data: archived = [] } = useQuery("/api/v1/todos/projects/", {
    params: { query: { archived: true } },
  });
  const inbox = projects.find((p) => p.is_inbox);
  const mine = projects.filter((p) => !p.is_inbox);
  const favourites = [
    ...mine
      .filter((p) => p.is_favourite)
      .map((p) => ({ key: p.id, name: p.name, href: `/todos/project?id=${p.id}`, icon: <Dot colour={p.colour} /> })),
    ...filters
      .filter((f) => f.is_favourite)
      .map((f) => ({ key: f.slug, name: f.name, href: `/todos/filter?slug=${f.slug}`, icon: <Star /> })),
    ...labels
      .filter((l) => l.is_favourite)
      .map((l) => ({
        key: l.id,
        name: l.name,
        href: `/todos/label?id=${l.id}`,
        icon: <Hash style={{ color: colourVar(l.colour) }} />,
      })),
  ];

  return (
    <>
      <List>
        <ListRow href="/todos" icon={<Inbox />} detail={inbox?.open_task_count || undefined}>
          Inbox
        </ListRow>
        <ListRow href="/todos/filters" icon={<Filter />}>
          Filters &amp; labels
        </ListRow>
        <ListRow href="/todos/templates" icon={<LayoutTemplate />}>
          Templates
        </ListRow>
      </List>
      {favourites.length > 0 && (
        <List title="Favourites">
          {favourites.map((f) => (
            <ListRow key={f.key} href={f.href} icon={f.icon}>
              {f.name}
            </ListRow>
          ))}
        </List>
      )}
      <List title="My projects" action={<NewProject />}>
        <ProjectTree projects={mine} />
        {mine.length === 0 && <ListRow>No projects yet.</ListRow>}
      </List>
      {archived.length > 0 && (
        <List title="Archived">
          {archived.map((p) => (
            <ListRow key={p.id} href={`/todos/project?id=${p.id}`} icon={<Archive />}>
              {p.name}
            </ListRow>
          ))}
        </List>
      )}
    </>
  );
}

function ProjectTree({ projects, parent = null, depth = 0 }: { projects: Project[]; parent?: string | null; depth?: number }) {
  return projects
    .filter((p) => (p.parent ?? null) === parent)
    .map((p) => (
      <div key={p.id} className="contents">
        <ListRow
          href={`/todos/project?id=${p.id}`}
          icon={<Dot colour={p.colour} />}
          detail={p.open_task_count || undefined}
          indent={depth}
        >
          <span className="flex items-center gap-1.5">
            <span className="truncate">{p.name}</span>
            {p.is_shared && <Users aria-label="Shared" className="text-muted-foreground size-3.5 shrink-0" />}
          </span>
        </ListRow>
        <ProjectTree projects={projects} parent={p.id} depth={depth + 1} />
      </div>
    ));
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
