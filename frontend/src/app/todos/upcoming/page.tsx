"use client";

import {
  DndContext,
  MouseSensor,
  pointerWithin,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { closeTask, reopenTask, updateTask } from "@/app/todos/actions";
import { addDays, dayName, dueText, isoDate } from "@/app/todos/due";
import { useTodos, type Task } from "@/app/todos/shell";
import { TaskCheck, TaskMeta, useClickGuard } from "@/app/todos/task-list";
import { Pending } from "@/components/app/pending";
import { AppBar, Screen } from "@/components/app/frame";
import { Button } from "@/components/ui/button";
import { InlineMarkdown } from "@/components/markdown/inline";
import { useQuery } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/**
 * A week strip, then one heading per day, overdue first. Dragging a task to
 * another day moves it there, keeping its time.
 */
export default function UpcomingPage() {
  const today = isoDate();
  // Seven days at a time, from today.
  const [from, setFrom] = useState(today);
  const to = addDays(from, 6);
  const { data: tasks, error } = useQuery("/api/v1/todos/tasks/", {
    params: { query: { view: "upcoming", from, to } },
  });
  const { data: overdue = [] } = useQuery("/api/v1/todos/tasks/", { params: { query: { filter: "overdue" } } });
  const sensors = useSensors(
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
  );
  // Where dropped tasks now are, until the refetched list agrees.
  const [moved, setMoved] = useState(new Map<string, string>());
  const days = Array.from({ length: 7 }, (_, i) => addDays(from, i));
  const late = new Set(overdue.map((t) => t.id));
  const all = [...new Map([...overdue, ...(tasks ?? [])].map((t) => [t.id, t])).values()];
  // Overdue tasks sit under Overdue until dropped on a day.
  const dayOf = (task: Task) => moved.get(task.id) ?? (late.has(task.id) ? null : task.due_date);

  async function drop({ active, over }: DragEndEvent) {
    const task = all.find((t) => t.id === active.id);
    const day = over?.id as string | undefined;
    if (!task || !day || day === task.due_date) return;
    setMoved((m) => new Map(m).set(task.id, day));
    const { error } = await updateTask(task.id, { due_date: day });
    if (error) toast.error(error);
    setMoved((m) => {
      const next = new Map(m);
      next.delete(task.id);
      return next;
    });
  }

  return (
    <>
      <AppBar title="Upcoming" />
      <Screen className="gap-4">
        <nav className="flex items-center gap-1" aria-label="Weeks">
          <Button variant="ghost" size="icon-sm" aria-label="Previous week" disabled={from <= today} onClick={() => setFrom(addDays(from, -7))}>
            <ChevronLeft />
          </Button>
          <ol className="grid flex-1 grid-cols-7 text-center text-xs">
            {days.map((day) => (
              <li key={day}>
                <a
                  href={`#day-${day}`}
                  className={cn(
                    "flex flex-col items-center rounded-lg py-1",
                    day === today && "text-primary font-semibold",
                  )}
                >
                  {new Date(`${day}T12:00:00`).toLocaleDateString("en-GB", { weekday: "narrow" })}
                  <span className="text-base tabular-nums">{Number(day.slice(8))}</span>
                </a>
              </li>
            ))}
          </ol>
          <Button variant="ghost" size="icon-sm" aria-label="Next week" onClick={() => setFrom(addDays(from, 7))}>
            <ChevronRight />
          </Button>
        </nav>

        <DndContext sensors={sensors} collisionDetection={pointerWithin} onDragEnd={drop}>
          {from === today && overdue.length > 0 && (
            <DaySection title="Overdue" tasks={all.filter((t) => late.has(t.id) && !dayOf(t))} />
          )}
          {!tasks && <Pending error={error} />}
          {tasks &&
            days.map((day) => (
              <DaySection
                key={day}
                day={day}
                title={`${new Date(`${day}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} · ${dayName(day, today)}`}
                tasks={all.filter((t) => dayOf(t) === day)}
              />
            ))}
        </DndContext>
      </Screen>
    </>
  );
}

function DaySection({ day, title, tasks }: { day?: string; title: string; tasks: Task[] }) {
  const { quickAdd } = useTodos();
  const { setNodeRef, isOver } = useDroppable({ id: day ?? "overdue", disabled: !day });
  return (
    <section id={day && `day-${day}`} ref={setNodeRef} className={cn("scroll-mt-16 rounded-lg", isOver && "bg-accent")}>
      <h2 className={cn("flex min-h-10 items-center border-b text-sm font-semibold", !day && "text-destructive")}>{title}</h2>
      <ul>
        {tasks.map((task) => (
          <DayRow key={task.id} task={task} />
        ))}
      </ul>
      {day && (
        <button
          type="button"
          className="text-muted-foreground active:bg-accent flex min-h-12 w-full items-center gap-3 text-sm"
          onClick={() => quickAdd({ due: day })}
        >
          <Plus className="text-primary size-5" /> Add task
        </button>
      )}
    </section>
  );
}

/** A task to tick off, open, or hold and drag to another day. */
function DayRow({ task }: { task: Task }) {
  const { setNodeRef, listeners, isDragging, transform } = useDraggable({ id: task.id });
  const [done, setDone] = useState(false);
  const guard = useClickGuard(isDragging);

  async function complete() {
    setDone(true);
    const { data, error } = await closeTask(task.id);
    if (error) {
      setDone(false);
      return toast.error(error);
    }
    const next = data && !data.completed_at && data.due_date;
    if (next) setDone(false);
    toast(next ? `Completed; next on ${dueText(next, data.due_time)}` : "Task completed", {
      duration: 8000,
      action: {
        label: "Undo",
        onClick: async () => {
          const undone = await reopenTask(task.id);
          if (undone.error) toast.error(undone.error);
          setDone(false);
        },
      },
    });
  }

  if (done) return null;
  return (
    <li
      ref={setNodeRef}
      {...listeners}
      onClickCapture={guard}
      className={cn("relative flex items-start gap-3 border-b py-3 select-none [-webkit-touch-callout:none]", isDragging && "bg-background z-10 shadow-lg")}
      style={{ transform: CSS.Translate.toString(transform) }}
    >
      <TaskCheck task={task} onComplete={complete} />
      <Link href={`/todos/task?id=${task.id}`} className="min-w-0 flex-1">
        <span className="block break-words">
          <InlineMarkdown source={task.content} />
        </span>
        <TaskMeta task={task} />
      </Link>
    </li>
  );
}
