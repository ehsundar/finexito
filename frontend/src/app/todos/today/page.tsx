"use client";

import { toast } from "sonner";

import { rescheduleTasks } from "@/app/todos/actions";
import { isoDate } from "@/app/todos/due";
import { TaskList, type Group } from "@/app/todos/task-list";
import { Pending } from "@/components/app/pending";
import { AppBar, Screen } from "@/components/app/frame";
import { Button } from "@/components/ui/button";
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { useQuery } from "@/lib/api/client";

/** Overdue, oldest first, then today's: timed ones by time, the rest by priority. */
export default function TodayPage() {
  const { data: tasks, error } = useQuery("/api/v1/todos/tasks/", { params: { query: { view: "today" } } });
  if (!tasks) return <Pending error={error} />;
  const overdue = tasks.filter((t) => t.is_overdue && t.due_date! < isoDate());
  const today = tasks.filter((t) => !overdue.includes(t));

  const groups: Group[] = [];
  if (overdue.length)
    groups.push({
      key: "overdue",
      title: (
        <>
          <h2 className="flex-1 text-sm font-semibold">Overdue</h2>
          <Button
            variant="link"
            size="sm"
            onClick={async () => {
              const { error } = await rescheduleTasks(
                overdue.map((t) => t.id),
                isoDate(),
              );
              if (error) toast.error(error);
            }}
          >
            Reschedule to today
          </Button>
        </>
      ),
      tasks: overdue,
    });
  if (today.length) groups.push({ key: "today", title: <h2 className="text-sm font-semibold">Today</h2>, tasks: today });

  return (
    <>
      <AppBar title="Today" />
      <Screen>
        {groups.length ? (
          <TaskList groups={groups} sort="given" />
        ) : (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>Nothing due today.</EmptyTitle>
            </EmptyHeader>
          </Empty>
        )}
      </Screen>
    </>
  );
}
