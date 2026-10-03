import { notFound } from "next/navigation";

import { TaskEditor } from "@/app/todos/task-editor";
import type { Task } from "@/app/todos/shell";
import { TaskList } from "@/app/todos/task-list";
import { AppBar, Screen } from "@/components/app/frame";
import { Markdown } from "@/components/markdown/markdown";
import { sessionApi } from "@/lib/auth/current-user";

export default async function TaskPage({ params }: PageProps<"/todos/tasks/[id]">) {
  const { id } = await params;
  const api = await sessionApi();
  const { data: task } = await api.GET("/api/v1/todos/tasks/{id}/", { params: { path: { id } } });
  if (!task) notFound();
  const [{ data: project }, { data: siblings = [] }] = await Promise.all([
    api.GET("/api/v1/todos/projects/{id}/", { params: { path: { id: task.project } } }),
    api.GET("/api/v1/todos/tasks/", { params: { query: { project: task.project } } }),
  ]);

  // Open sub-tasks at every level below this one.
  const below: Task[] = [];
  const queue = [task.id];
  while (queue.length) {
    const parent = queue.shift();
    for (const t of siblings.filter((s) => s.parent === parent)) {
      below.push(t);
      queue.push(t.id);
    }
  }
  const parent = task.parent ? siblings.find((t) => t.id === task.parent) : undefined;

  return (
    <>
      <AppBar
        back={
          parent
            ? `/todos/tasks/${parent.id}`
            : project?.is_inbox
              ? "/todos"
              : `/todos/projects/${task.project}`
        }
        title={<span className="text-muted-foreground truncate text-base">{parent?.content ?? project?.name}</span>}
      />
      <Screen>
        <TaskEditor
          task={task}
          description={task.description ? <Markdown source={task.description} /> : null}
        />
        <TaskList
          groups={[
            {
              key: "subtasks",
              title: <h2 className="text-muted-foreground text-sm font-medium">Sub-tasks</h2>,
              tasks: below.map((t) => (t.parent === task.id ? { ...t, parent: null } : t)),
            },
          ]}
          parentTask={task}
        />
      </Screen>
    </>
  );
}
