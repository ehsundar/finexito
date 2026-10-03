import { notFound } from "next/navigation";

import { Board } from "@/app/todos/board";
import { CompletedList } from "@/app/todos/completed-list";
import { ProjectHeader, SectionTitle } from "@/app/todos/project-header";
import { TaskList, type Group } from "@/app/todos/task-list";
import { Screen } from "@/components/app/frame";
import { sessionApi } from "@/lib/auth/current-user";

/** A project, as a list or a board; the Inbox is one too. */
export async function ProjectView({ id, completed }: { id: string; completed: boolean }) {
  const api = await sessionApi();
  const project = id === "inbox" ? null : id;
  const [projects, found] = await Promise.all([
    project ? null : api.GET("/api/v1/todos/projects/"),
    project ? api.GET("/api/v1/todos/projects/{id}/", { params: { path: { id: project } } }) : null,
  ]);
  const current = found?.data ?? projects?.data?.find((p) => p.is_inbox);
  if (!current) notFound();

  const query = { project: current.id };
  const [sections, tasks, done] = await Promise.all([
    api.GET("/api/v1/todos/sections/", { params: { query } }),
    api.GET("/api/v1/todos/tasks/", { params: { query } }),
    completed
      ? api.GET("/api/v1/todos/tasks/", { params: { query: { ...query, completed: true } } })
      : null,
  ]);
  const allSections = sections.data ?? [];
  const allTasks = tasks.data ?? [];

  const groups: Group[] = [
    { key: "none", tasks: allTasks.filter((t) => !t.section), section: null },
    ...allSections.map((section) => ({
      key: section.id,
      section: section.id,
      title: <SectionTitle section={section} />,
      tasks: allTasks.filter((t) => t.section === section.id),
    })),
  ];

  return (
    <>
      <ProjectHeader project={current} showingCompleted={completed} />
      <Screen>
        {current.view === "board" ? (
          <Board project={current} sections={allSections} tasks={allTasks} />
        ) : (
          <TaskList groups={groups} sort={current.sort} project={current} />
        )}
        {done && <CompletedList tasks={done.data ?? []} />}
      </Screen>
    </>
  );
}
