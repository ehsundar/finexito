"use client";

import { useSearchParams } from "next/navigation";

import { Comments } from "@/app/todos/comments";
import { TaskEditor } from "@/app/todos/task-editor";
import type { Task } from "@/app/todos/shell";
import { TaskList } from "@/app/todos/task-list";
import { AppBar, Screen } from "@/components/app/frame";
import { Markdown } from "@/components/markdown/markdown";
import { useQuery } from "@/lib/api/client";

/** `?id=`: the task. */
export default function TaskPage() {
  const id = useSearchParams().get("id") ?? "";
  const { data: task, error } = useQuery("/api/v1/todos/tasks/{id}/", { params: { path: { id } } });
  const inProject = task ? { params: { path: { id: task.project } } } : null;
  const { data: project } = useQuery("/api/v1/todos/projects/{id}/", inProject);
  const { data: siblings } = useQuery(
    "/api/v1/todos/tasks/",
    task ? { params: { query: { project: task.project } } } : null,
  );
  if (error) return <Screen>This task doesn&apos;t exist.</Screen>;
  if (!task || !siblings) return null;

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
            ? `/todos/task?id=${parent.id}`
            : project?.is_inbox
              ? "/todos"
              : `/todos/project?id=${task.project}`
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
        {project && <Comments task={task.id} project={project} />}
      </Screen>
    </>
  );
}
