"use client";

import { CalendarDays, CalendarOff, Repeat, Sofa, Sun, Sunrise } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { parseDue, updateTask } from "@/app/todos/actions";
import type { Task } from "@/app/todos/shell";
import { List, ListRow } from "@/components/app/list";
import { Sheet } from "@/components/app/sheet";
import { Input } from "@/components/ui/input";
import type { components } from "@/lib/api/schema";

type Due = components["schemas"]["Due"];

/** A day as the API writes it, `2026-10-07`, in this device's time zone. */
export function isoDate(date = new Date()) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Noon on that day, so adding days never trips over a change of clocks. */
const noon = (iso: string) => new Date(`${iso}T12:00:00`);

export function addDays(iso: string, days: number) {
  const date = noon(iso);
  date.setDate(date.getDate() + days);
  return isoDate(date);
}

const daysBetween = (from: string, to: string) => Math.round((noon(to).getTime() - noon(from).getTime()) / 86_400_000);

/** *Today*, *Tomorrow*, a weekday within the week, else `12 Oct`, with the year if it isn't this one. */
export function dayName(iso: string, today = isoDate()) {
  const days = daysBetween(today, iso);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days === -1) return "Yesterday";
  const date = noon(iso);
  if (days > 1 && days < 7) return date.toLocaleDateString("en-GB", { weekday: "long" });
  const sameYear = iso.slice(0, 4) === today.slice(0, 4);
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: sameYear ? undefined : "numeric" });
}

export function dueText(date: string, time?: string | null) {
  return time ? `${dayName(date)} ${time.slice(0, 5)}` : dayName(date);
}

/** A task's date, in the danger colour once it's overdue. */
export function DueLabel({ task }: { task: Task }) {
  if (!task.due_date) return null;
  return (
    <span className="inline-flex items-center gap-1" style={task.is_overdue ? { color: "var(--destructive)" } : undefined}>
      <CalendarDays className="size-3" />
      {dueText(task.due_date, task.due_time)}
      {task.is_recurring && <Repeat className="size-3" aria-label="Recurring" />}
    </span>
  );
}

/** What a typed phrase means, asked of the server while typing. */
export function useParsedDue(text: string, find = false) {
  const [result, setResult] = useState<{ text: string; due?: Due | null; match?: number[] | null; content?: string; error?: string } | null>(null);
  useEffect(() => {
    if (!text.trim()) return;
    const timer = setTimeout(async () => {
      const { data, error } = await parseDue(text, find);
      setResult({ text, error, due: data?.due, match: data?.match, content: data?.content });
    }, 250);
    return () => clearTimeout(timer);
  }, [text, find]);
  // A result for older text is stale.
  return text.trim() && result?.text === text ? result : null;
}

const QUICK = [
  { label: "Today", phrase: "today", icon: <Sun /> },
  { label: "Tomorrow", phrase: "tomorrow", icon: <Sunrise /> },
  { label: "This weekend", phrase: "this weekend", icon: <Sofa /> },
  { label: "Next week", phrase: "next week", icon: <CalendarDays /> },
  { label: "No date", phrase: "no date", icon: <CalendarOff /> },
];

/** Sets a task's date: typed (`every monday 9am`), from the quick list, or picked. */
export function DueSheet({ task, ...props }: { task: Task; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [text, setText] = useState("");
  const parsed = useParsedDue(text);

  async function save(body: Parameters<typeof updateTask>[1]) {
    const { error } = await updateTask(task.id, body);
    if (error) return toast.error(error);
    setText("");
    props.onOpenChange(false);
  }

  return (
    <Sheet {...props} title="Due date" description={task.due_string ? `Now: ${task.due_string}` : undefined}>
      <form
        className="flex flex-col gap-1.5"
        onSubmit={(event) => {
          event.preventDefault();
          if (text.trim() && parsed && !parsed.error) save({ due_string: text.trim() });
        }}
      >
        <Input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Type a date: every friday 9am"
          enterKeyHint="done"
          aria-describedby="due-preview"
          className="h-11 text-base"
        />
        <p id="due-preview" className="text-muted-foreground min-h-5 px-1 text-sm">
          {parsed?.error
            ? "Couldn't understand that date"
            : parsed?.due?.date
              ? `${dueText(parsed.due.date, parsed.due.time)}${parsed.due.is_recurring ? ", repeating" : ""}`
              : parsed && "No date"}
        </p>
      </form>
      <List>
        {QUICK.map((q) => (
          <ListRow key={q.phrase} icon={q.icon} onClick={() => save({ due_string: q.phrase })}>
            {q.label}
          </ListRow>
        ))}
      </List>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1 text-sm">
          Date
          <Input
            type="date"
            key={`date-${task.due_date}`}
            defaultValue={task.due_date ?? ""}
            onChange={(event) => event.target.value && save({ due_date: event.target.value })}
            className="h-11 text-base"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Time
          <Input
            type="time"
            key={`time-${task.due_date}-${task.due_time}`}
            defaultValue={task.due_time ?? ""}
            disabled={!task.due_date}
            onBlur={(event) => {
              const time = event.target.value || null;
              if (time !== (task.due_time ?? null)) save({ due_time: time });
            }}
            className="h-11 text-base"
          />
        </label>
      </div>
    </Sheet>
  );
}
