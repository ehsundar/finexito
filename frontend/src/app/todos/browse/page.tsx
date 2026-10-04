"use client";

import { Archive, Bell, Filter, Hash, Inbox, LayoutTemplate, Star, Users } from "lucide-react";
import { useState } from "react";

import { NotificationSettingsSheet } from "@/app/todos/reminders";
import { colourVar, Dot, NewProject, useTodos, type Project } from "@/app/todos/shell";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";
import { useQuery } from "@/lib/api/client";

/** Everything to open: favourites, projects (as a tree), filters and labels. */
export default function BrowsePage() {
  const { projects, labels, filters } = useTodos();
  const { data: archived = [] } = useQuery("/api/v1/todos/projects/", {
    params: { query: { archived: true } },
  });
  const [settings, setSettings] = useState(false);
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
      <AppBar title="Browse" />
      <Screen>
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
          <ListRow icon={<Bell />} onClick={() => setSettings(true)}>
            Notifications
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
      </Screen>
      <NotificationSettingsSheet open={settings} onOpenChange={setSettings} />
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
