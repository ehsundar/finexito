"use client";

import {
  closestCenter,
  DndContext,
  MouseSensor,
  TouchSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronDown, ChevronRight, MessageSquare, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { closeTask, moveTask, reopenTask, reorder } from "@/app/todos/actions";
import { DueLabel, dueText } from "@/app/todos/due";
import { Avatar, usePeople } from "@/app/todos/people";
import { colourVar, useTodos, type Project, type Task } from "@/app/todos/shell";
import { InlineMarkdown } from "@/components/markdown/inline";
import { cn } from "@/lib/utils";

/** `given`: as the server listed them (Today, Upcoming), which can't be reordered. */
type Sort = NonNullable<Project["sort"]> | "given";

/** Display order only: the manual order stays as it is. */
export function sortTasks(tasks: Task[], sort: Sort = "manual") {
  if (sort === "given") return tasks;
  const by: Record<Exclude<Sort, "given">, (a: Task, b: Task) => number> = {
    manual: (a, b) => a.order - b.order,
    priority: (a, b) => (a.priority ?? 4) - (b.priority ?? 4) || a.order - b.order,
    name: (a, b) => a.content.localeCompare(b.content),
    added: (a, b) => a.created_at.localeCompare(b.created_at),
  };
  return [...tasks].sort(by[sort]);
}

export const priorityVar = (priority: Task["priority"]) => `var(--priority-${priority ?? 4})`;

export type Group = { key: string; title?: React.ReactNode; tasks: Task[]; section?: string | null };

/** Where a task sits: a dragged task changes place only among these. */
type Place = Pick<Task, "project" | "section" | "parent">;

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
  // Lifting a row: a long press on a phone, a short drag with a mouse.
  const sensors = useSensors(
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
  );
  const [dragging, setDragging] = useState<Task | null>(null);
  // Where dropped tasks now sit, shown until the refetched tasks agree or move on.
  const [pending, setPending] = useState(new Map<string, { was: Task; now: Partial<Task> }>());

  const shown = (tasks: Task[]) =>
    tasks
      .filter((t) => !hidden.has(t.id))
      .map((t) => {
        const move = pending.get(t.id);
        const unchanged = move && t.order === move.was.order && t.section === move.was.section;
        return unchanged ? { ...t, ...move.now } : t;
      });
  const all = shown(groups.flatMap((g) => g.tasks));
  // Only a project's list has sections to drag between.
  const sectioned = groups.some((g) => g.section !== undefined);
  const byId = new Map(all.map((t) => [t.id, t]));
  /** A task's section is its top task's, which a drop may just have changed. */
  const home = (task: Task) => {
    while (task.parent && byId.has(task.parent)) task = byId.get(task.parent)!;
    return task.section ?? null;
  };
  const fits = (task: Place, onto: Place) =>
    task.project === onto.project &&
    task.parent === onto.parent &&
    (task.section === onto.section || (sectioned && !task.parent));

  async function complete(task: Task) {
    setHidden((h) => new Set(h).add(task.id));
    const { data, error } = await closeTask(task.id);
    if (error) {
      setHidden((h) => withoutId(h, task.id));
      return toast.error(error);
    }
    // A recurring task stays open, on its next date.
    const next = data && !data.completed_at && data.due_date;
    if (next) setHidden((h) => withoutId(h, task.id));
    toast(next ? `Completed; next on ${dueText(next, data.due_time)}` : "Task completed", {
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

  /** Puts the task before or after the row it was dropped on, or at the end of an empty section. */
  async function drop({ active, over }: DragEndEvent) {
    setDragging(null);
    const moved = all.find((t) => t.id === active.id);
    if (!moved || !over || over.id === active.id) return;
    const target = all.find((t) => t.id === over.id);
    const section = target ? target.section : (groups.find((g) => g.key === over.id)?.section ?? null);
    const siblings = all.filter(
      (t) => t.id !== moved.id && t.project === moved.project && t.parent === moved.parent && t.section === section,
    );
    const ids = sortTasks(siblings).map((t) => t.id);
    const below = (active.rect.current.translated?.top ?? 0) > over.rect.top;
    const index = target ? ids.indexOf(target.id) + (below ? 1 : 0) : ids.length;
    ids.splice(index, 0, moved.id);

    const now = new Map(ids.map((id, i) => [id, { order: i + 1 } as Partial<Task>]));
    now.set(moved.id, { order: index + 1, section });
    setPending(new Map(ids.map((id) => [id, { was: all.find((t) => t.id === id)!, now: now.get(id)! }])));
    const { error } =
      section === moved.section ? await reorder("tasks", ids) : await moveTask(moved.id, { section }, ids);
    if (error) {
      setPending(new Map());
      toast.error(error);
    }
  }

  const branch = (tasks: Task[], parent: string | null, depth: number): React.ReactNode => {
    const ids = new Set(tasks.map((t) => t.id));
    // A sub-task whose parent isn't listed (a filter, a search) shows at the top.
    const level = sortTasks(
      tasks.filter((t) => (t.parent && ids.has(t.parent) ? t.parent : null) === parent),
      sort,
    );
    return (
      <SortableContext items={level.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        {level.map((task) => (
          <TaskRow
            key={task.id}
            task={task}
            depth={depth}
            draggable={sort === "manual"}
            droppable={!!dragging && fits(task, dragging)}
            collapsed={collapsed.has(task.id)}
            onToggle={() =>
              setCollapsed((c) => (c.has(task.id) ? withoutId(c, task.id) : new Set(c).add(task.id)))
            }
            onComplete={() => complete(task)}
          >
            {task.subtask_count > 0 && !collapsed.has(task.id) && (
              <ul>{branch(tasks, task.id, depth + 1)}</ul>
            )}
          </TaskRow>
        ))}
      </SortableContext>
    );
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[({ transform }) => ({ ...transform, x: 0 })]}
      onDragStart={({ active }) => setDragging(all.find((t) => t.id === active.id) ?? null)}
      onDragCancel={() => setDragging(null)}
      onDragEnd={drop}
    >
      {groups.map((group) => {
        const tasks = sectioned
          ? all.filter((t) => home(t) === (group.section ?? null))
          : all.filter((t) => group.tasks.some((g) => g.id === t.id));
        return (
          <section key={group.key}>
            {group.title && <div className="flex min-h-10 items-center border-b">{group.title}</div>}
            <GroupList
              id={group.key}
              // An empty section takes a dropped task; a full one has rows to drop on.
              droppable={
                !!dragging && !tasks.length && fits(dragging, { ...dragging, section: group.section ?? null })
              }
            >
              {branch(tasks, null, 0)}
            </GroupList>
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
        );
      })}
    </DndContext>
  );
}

/**
 * Releasing a dragged row ends in a click on it, which would open the task.
 * Put the returned handler on the row's `onClickCapture` to swallow that click.
 */
export function useClickGuard(isDragging: boolean) {
  const dragged = useRef(false);
  useEffect(() => {
    if (isDragging) dragged.current = true;
    // The click comes straight after the release, if at all; a later tap is real.
    else if (dragged.current) {
      const timer = setTimeout(() => (dragged.current = false), 100);
      return () => clearTimeout(timer);
    }
  }, [isDragging]);
  return (event: React.MouseEvent) => {
    if (!dragged.current) return;
    dragged.current = false;
    event.preventDefault();
    event.stopPropagation();
  };
}

export function withoutId(ids: Set<string>, id: string) {
  const next = new Set(ids);
  next.delete(id);
  return next;
}

function TaskRow({
  task,
  depth,
  draggable,
  droppable,
  collapsed,
  onToggle,
  onComplete,
  children,
}: {
  task: Task;
  depth: number;
  draggable: boolean;
  droppable: boolean;
  collapsed: boolean;
  onToggle: () => void;
  onComplete: () => void;
  children: React.ReactNode;
}) {
  const { setNodeRef, listeners, isDragging, transform, transition } = useSortable({
    id: task.id,
    disabled: { draggable: !draggable, droppable: !droppable },
  });
  const guard = useClickGuard(isDragging);
  return (
    <li
      ref={setNodeRef}
      {...listeners}
      onClickCapture={guard}
      // A long press lifts the row, rather than selecting text or opening the link's menu.
      className={cn("relative select-none [-webkit-touch-callout:none]", isDragging && "bg-background z-10 shadow-lg")}
      style={{ transform: CSS.Translate.toString(transform), transition }}
    >
      <div className="flex items-start gap-3 border-b py-3" style={{ paddingLeft: `${depth * 1.5}rem` }}>
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
      </div>
      {children}
    </li>
  );
}

function GroupList({ id, droppable, children }: { id: string; droppable: boolean; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled: !droppable });
  return (
    <ul ref={setNodeRef} className={cn(droppable && "min-h-12", isOver && "bg-accent")}>
      {children}
    </ul>
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
  const { labels, projects } = useTodos();
  const own = labels.filter((l) => task.labels?.includes(l.id));
  const people = usePeople(task.assignee ? projects.find((p) => p.id === task.project) : undefined);
  const assignee = people.find((p) => p.id === task.assignee);
  if (!task.subtask_count && !own.length && !task.description && !task.due_date && !task.comment_count && !assignee)
    return null;
  return (
    <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      {assignee && <Avatar person={assignee} className="size-4 text-[8px]" />}
      <DueLabel task={task} />
      {task.subtask_count > 0 && (
        <span className="tabular-nums">
          {task.completed_subtask_count}/{task.subtask_count}
        </span>
      )}
      {task.description && <span aria-label="Has a description">≡</span>}
      {task.comment_count > 0 && (
        <span className="flex items-center gap-0.5 tabular-nums" aria-label={`${task.comment_count} comments`}>
          <MessageSquare className="size-3" />
          {task.comment_count}
        </span>
      )}
      {own.map((l) => (
        <span key={l.id} style={{ color: colourVar(l.colour) }}>
          #{l.name}
        </span>
      ))}
    </div>
  );
}
