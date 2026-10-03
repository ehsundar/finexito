"use client";

import { ChevronDown, ChevronRight, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { closeTask, reopenTask } from "@/app/todos/actions";
import { colourVar, useTodos, type Project, type Task } from "@/app/todos/shell";
import { InlineMarkdown } from "@/components/markdown/inline";

type Sort = NonNullable<Project["sort"]>;

/** Display order only: the manual order stays as it is. */
export function sortTasks(tasks: Task[], sort: Sort = "manual") {
  const by: Record<Sort, (a: Task, b: Task) => number> = {
    manual: (a, b) => a.order - b.order,
    priority: (a, b) => (a.priority ?? 4) - (b.priority ?? 4) || a.order - b.order,
    name: (a, b) => a.content.localeCompare(b.content),
    added: (a, b) => a.created_at.localeCompare(b.created_at),
  };
  return [...tasks].sort(by[sort]);
}

export const priorityVar = (priority: Task["priority"]) => `var(--priority-${priority ?? 4})`;

/** Tasks in the order they appear, with how deep each sits. */
function flatten(tasks: Task[], sort: Sort, collapsed: Set<string>) {
  const under = new Map<string | null, Task[]>();
  const ids = new Set(tasks.map((t) => t.id));
  for (const task of tasks) {
    // A sub-task whose parent isn't listed (a filter, a search) shows at the top.
    const parent = task.parent && ids.has(task.parent) ? task.parent : null;
    under.set(parent, [...(under.get(parent) ?? []), task]);
  }
  const rows: { task: Task; depth: number }[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const task of sortTasks(under.get(parent) ?? [], sort)) {
      rows.push({ task, depth });
      if (!collapsed.has(task.id)) walk(task.id, depth + 1);
    }
  };
  walk(null, 0);
  return rows;
}

export type Group = { key: string; title?: React.ReactNode; tasks: Task[]; section?: string | null };

/** Tasks in groups (a project's sections, or a filter's projects), each a tree. */
export function TaskList({
  groups,
  sort = "manual",
  project,
  parentTask,
}: {
  groups: Group[];
  sort?: Sort;
  /** Where "Add task" puts new tasks: a project's sections, or under a task. */
  project?: Project;
  parentTask?: Task;
}) {
  const { quickAdd } = useTodos();
  const [collapsed, setCollapsed] = useState(new Set<string>());
  const [hidden, setHidden] = useState(new Set<string>());

  async function complete(task: Task) {
    setHidden((h) => new Set(h).add(task.id));
    const { error } = await closeTask(task.id);
    if (error) {
      setHidden((h) => withoutId(h, task.id));
      return toast.error(error);
    }
    toast("Task completed", {
      duration: 8000,
      action: {
        label: "Undo",
        onClick: async () => {
          const undone = await reopenTask(task.id);
          if (undone.error) toast.error(undone.error);
          setHidden((h) => withoutId(h, task.id));
        },
      },
    });
  }

  return groups.map((group) => (
    <section key={group.key}>
      {group.title && <div className="flex min-h-10 items-center border-b">{group.title}</div>}
      <ul>
        {flatten(
          group.tasks.filter((t) => !hidden.has(t.id)),
          sort,
          collapsed,
        ).map(({ task, depth }) => (
          <TaskRow
            key={task.id}
            task={task}
            depth={depth}
            collapsed={collapsed.has(task.id)}
            onToggle={() =>
              setCollapsed((c) => (c.has(task.id) ? withoutId(c, task.id) : new Set(c).add(task.id)))
            }
            onComplete={() => complete(task)}
          />
        ))}
      </ul>
      {(project || parentTask) && (
        <button
          type="button"
          className="text-muted-foreground active:bg-accent flex min-h-12 w-full items-center gap-3 text-sm"
          onClick={() =>
            quickAdd(
              parentTask
                ? { project: parentTask.project, section: parentTask.section ?? undefined, parent: parentTask.id }
                : { project: project?.id, section: group.section ?? undefined },
            )
          }
        >
          <Plus className="text-primary size-5" /> {parentTask ? "Add sub-task" : "Add task"}
        </button>
      )}
    </section>
  ));
}

export function withoutId(ids: Set<string>, id: string) {
  const next = new Set(ids);
  next.delete(id);
  return next;
}

function TaskRow({
  task,
  depth,
  collapsed,
  onToggle,
  onComplete,
}: {
  task: Task;
  depth: number;
  collapsed: boolean;
  onToggle: () => void;
  onComplete: () => void;
}) {
  return (
    <li className="flex items-start gap-3 border-b py-3" style={{ paddingLeft: `${depth * 1.5}rem` }}>
      <TaskCheck task={task} onComplete={onComplete} />
      <Link href={`/todos/task?id=${task.id}`} className="min-w-0 flex-1">
        <span className="block break-words">
          <InlineMarkdown source={task.content} />
        </span>
        <TaskMeta task={task} />
      </Link>
      {task.subtask_count > 0 && (
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Show sub-tasks" : "Hide sub-tasks"}
          className="text-muted-foreground -my-1 p-1"
        >
          {collapsed ? <ChevronRight className="size-5" /> : <ChevronDown className="size-5" />}
        </button>
      )}
    </li>
  );
}

export function TaskCheck({ task, onComplete }: { task: Task; onComplete: () => void }) {
  const done = !!task.completed_at;
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={done}
      aria-label={done ? "Completed" : "Complete"}
      onClick={(event) => {
        event.stopPropagation();
        onComplete();
      }}
      className="-m-1.5 shrink-0 p-1.5"
    >
      <span
        className="flex size-5 rounded-full border-2"
        style={{
          borderColor: priorityVar(task.priority),
          background: done ? priorityVar(task.priority) : undefined,
        }}
      />
    </button>
  );
}

export function TaskMeta({ task }: { task: Task }) {
  const { labels } = useTodos();
  const own = labels.filter((l) => task.labels?.includes(l.id));
  if (!task.subtask_count && !own.length && !task.description) return null;
  return (
    <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      {task.subtask_count > 0 && (
        <span className="tabular-nums">
          {task.completed_subtask_count}/{task.subtask_count}
        </span>
      )}
      {task.description && <span aria-label="Has a description">≡</span>}
      {own.map((l) => (
        <span key={l.id} style={{ color: colourVar(l.colour) }}>
          #{l.name}
        </span>
      ))}
    </div>
  );
}
