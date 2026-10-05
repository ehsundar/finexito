"use client";

import { useSearchParams } from "next/navigation";

import { Board } from "@/app/todos/board";
import { CompletedList } from "@/app/todos/completed-list";
import { ProjectHeader, SectionTitle } from "@/app/todos/project-header";
import { useTodos } from "@/app/todos/shell";
import { TaskList, type Group } from "@/app/todos/task-list";
import { Pending } from "@/components/app/pending";
import { Screen } from "@/components/app/frame";
import { useQuery } from "@/lib/api/client";

/** A project, as a list or a board; the Inbox is the one without an `id`. */
export function ProjectView() {
  const params = useSearchParams();
  const id = params.get("id");
  const completed = params.has("completed");
  const { projects } = useTodos();
  // By id, since archived projects aren't in the shell's list.
  const found = useQuery("/api/v1/todos/projects/{id}/", id ? { params: { path: { id } } } : null);
  const current = id ? found.data : projects.find((p) => p.is_inbox);
  const query = current ? { params: { query: { project: current.id } } } : null;
  const { data: allSections, error: sectionsError } = useQuery("/api/v1/todos/sections/", query);
  const { data: allTasks, error: tasksError } = useQuery("/api/v1/todos/tasks/", query);
  const { data: done, error: doneError } = useQuery(
    "/api/v1/todos/tasks/",
    current && completed ? { params: { query: { project: current.id, completed: true } } } : null,
  );
  if (!current || !allSections || !allTasks) {
    return <Pending error={found.error ?? sectionsError ?? tasksError} missing="This project doesn’t exist." />;
  }

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
        {completed && (done ? <CompletedList tasks={done} /> : <Pending error={doneError} />)}
      </Screen>
    </>
  );
}
