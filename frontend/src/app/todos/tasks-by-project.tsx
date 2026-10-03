"use client";

import Link from "next/link";

import { useTodos, type Project, type Task } from "@/app/todos/shell";
import { TaskList, type Group } from "@/app/todos/task-list";
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

/** Tasks from many projects (a filter, a label, a search), grouped by project. */
export function TasksByProject({ tasks, empty }: { tasks: Task[]; empty: string }) {
  const { projects } = useTodos();
  const byId = new Map<string, Project>(projects.map((p) => [p.id, p]));
  const groups: Group[] = [];
  for (const task of tasks) {
    let group = groups.find((g) => g.key === task.project);
    if (!group) {
      const project = byId.get(task.project);
      const href = project?.is_inbox ? "/todos" : `/todos/project?id=${task.project}`;
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
