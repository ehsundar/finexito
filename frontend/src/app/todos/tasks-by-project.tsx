import Link from "next/link";

import type { Project, Task } from "@/app/todos/shell";
import { TaskList, type Group } from "@/app/todos/task-list";
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { sessionApi } from "@/lib/auth/current-user";

/** Tasks from many projects (a filter, a label, a search), grouped by project. */
export async function TasksByProject({ tasks, empty }: { tasks: Task[]; empty: string }) {
  const { data: projects = [] } = await (await sessionApi()).GET("/api/v1/todos/projects/");
  const byId = new Map<string, Project>(projects.map((p) => [p.id, p]));
  const groups: Group[] = [];
  for (const task of tasks) {
    let group = groups.find((g) => g.key === task.project);
    if (!group) {
      const project = byId.get(task.project);
      const href = project?.is_inbox ? "/todos" : `/todos/projects/${task.project}`;
      group = {
        key: task.project,
        title: (
          <Link href={href} className="flex-1 text-sm font-semibold">
            {project?.name ?? "Project"}
          </Link>
        ),
        tasks: [],
      };
      groups.push(group);
    }
    group.tasks.push(task);
  }
  if (!groups.length) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>{empty}</EmptyTitle>
        </EmptyHeader>
      </Empty>
    );
  }
  return <TaskList groups={groups} />;
}
