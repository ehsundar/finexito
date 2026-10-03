import { Archive, Filter, Hash, Inbox, Star } from "lucide-react";

import { colourVar, Dot, NewProject, type Project } from "@/app/todos/shell";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";
import { sessionApi } from "@/lib/auth/current-user";

export const metadata = { title: "Browse" };

/** Everything to open: favourites, projects (as a tree), filters and labels. */
export default async function BrowsePage() {
  const api = await sessionApi();
  const [{ data: projects = [] }, { data: archived = [] }, { data: labels = [] }, { data: filters = [] }] =
    await Promise.all([
      api.GET("/api/v1/todos/projects/"),
      api.GET("/api/v1/todos/projects/", { params: { query: { archived: true } } }),
      api.GET("/api/v1/todos/labels/"),
      api.GET("/api/v1/todos/filters/"),
    ]);
  const inbox = projects.find((p) => p.is_inbox);
  const mine = projects.filter((p) => !p.is_inbox);
  const favourites = [
    ...mine
      .filter((p) => p.is_favourite)
      .map((p) => ({ key: p.id, name: p.name, href: `/todos/projects/${p.id}`, icon: <Dot colour={p.colour} /> })),
    ...filters
      .filter((f) => f.is_favourite)
      .map((f) => ({ key: f.slug, name: f.name, href: `/todos/filters/${f.slug}`, icon: <Star /> })),
    ...labels
      .filter((l) => l.is_favourite)
      .map((l) => ({
        key: l.id,
        name: l.name,
        href: `/todos/labels/${l.id}`,
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
              <ListRow key={p.id} href={`/todos/projects/${p.id}`} icon={<Archive />}>
                {p.name}
              </ListRow>
            ))}
          </List>
        )}
      </Screen>
    </>
  );
}

function ProjectTree({ projects, parent = null, depth = 0 }: { projects: Project[]; parent?: string | null; depth?: number }) {
  return projects
    .filter((p) => (p.parent ?? null) === parent)
    .map((p) => (
      <div key={p.id} className="contents">
        <ListRow
          href={`/todos/projects/${p.id}`}
          icon={<Dot colour={p.colour} />}
          detail={p.open_task_count || undefined}
          indent={depth}
        >
          {p.name}
        </ListRow>
        <ProjectTree projects={projects} parent={p.id} depth={depth + 1} />
      </div>
    ));
}
