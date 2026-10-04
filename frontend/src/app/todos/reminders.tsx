"use client";

import { Bell, Check, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { addReminder, deleteReminder, updateProfile } from "@/app/todos/actions";
import type { Task } from "@/app/todos/shell";
import { List, ListRow } from "@/components/app/list";
import { Sheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useQuery } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Reminder = components["schemas"]["Reminder"];

const BEFORE = [0, 10, 30, 60, 24 * 60];

export function beforeText(minutes: number) {
  if (minutes === 0) return "At the time";
  if (minutes % (24 * 60) === 0) return `${minutes / (24 * 60)} day${minutes === 1440 ? "" : "s"} before`;
  if (minutes % 60 === 0) return `${minutes / 60} hour${minutes === 60 ? "" : "s"} before`;
  return `${minutes} minutes before`;
}

export function reminderText(reminder: Reminder) {
  if (reminder.minutes_before != null) return beforeText(reminder.minutes_before);
  return new Date(reminder.at!).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

/** A task's reminders: relative to its time, or at a moment. */
export function useReminders(task: Task) {
  return useQuery("/api/v1/todos/tasks/{id}/reminders/", { params: { path: { id: task.id } } });
}

export function RemindersSheet({ task, ...props }: { task: Task; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data: reminders = [] } = useReminders(task);
  const [at, setAt] = useState("");
  const taken = new Set(reminders.map((r) => r.minutes_before));

  async function add(body: Parameters<typeof addReminder>[1]) {
    const { error } = await addReminder(task.id, body);
    if (error) toast.error(error);
    return !error;
  }

  return (
    <Sheet {...props} title="Reminders" description="By email, when each one is due.">
      {reminders.length > 0 && (
        <List>
          {reminders.map((r) => (
            <ListRow
              key={r.id}
              icon={<Bell />}
              trailing={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Remove reminder"
                  onClick={async () => {
                    const { error } = await deleteReminder(r.id);
                    if (error) toast.error(error);
                  }}
                >
                  <X />
                </Button>
              }
            >
              {reminderText(r)}
            </ListRow>
          ))}
        </List>
      )}
      <List title={task.due_time ? "Before the task's time" : "Give the task a time to be reminded before it"}>
        {task.due_time &&
          BEFORE.filter((m) => !taken.has(m)).map((m) => (
            <ListRow key={m} onClick={() => add({ minutes_before: m })}>
              {beforeText(m)}
            </ListRow>
          ))}
      </List>
      <form
        className="flex gap-2"
        onSubmit={async (event) => {
          event.preventDefault();
          if (at && (await add({ at: new Date(at).toISOString() }))) setAt("");
        }}
      >
        <Input
          type="datetime-local"
          value={at}
          onChange={(event) => setAt(event.target.value)}
          aria-label="Remind me at"
          className="h-11 flex-1 text-base"
        />
        <Button type="submit" size="lg" className="h-11" disabled={!at}>
          Add
        </Button>
      </form>
    </Sheet>
  );
}

const DEFAULTS = [
  { value: "off", label: "Off" },
  { value: "0", label: "At the time" },
  { value: "10", label: "10 minutes before" },
  { value: "30", label: "30 minutes before" },
  { value: "60", label: "1 hour before" },
];

/** The member's reminder preferences, kept in their profile. */
export function ReminderSettingsSheet(props: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data: profile } = useQuery("/api/v1/profiles/me/");
  const current = profile?.extra?.todos_reminder_before ?? "30";
  const emails = profile?.extra?.todos_reminder_emails !== "false";

  async function save(extra: Record<string, string>) {
    const { error } = await updateProfile(extra);
    if (error) toast.error(error);
  }

  return (
    <Sheet {...props} title="Reminders">
      <List title="Remind me of timed tasks">
        {DEFAULTS.map((d) => (
          <ListRow
            key={d.value}
            onClick={() => save({ todos_reminder_before: d.value })}
            detail={current === d.value ? <Check className="text-primary size-4" /> : undefined}
          >
            {d.label}
          </ListRow>
        ))}
      </List>
      <List>
        <ListRow
          onClick={() => save({ todos_reminder_emails: emails ? "false" : "true" })}
          detail={emails ? "On" : "Off"}
        >
          Reminder emails
        </ListRow>
      </List>
    </Sheet>
  );
}
