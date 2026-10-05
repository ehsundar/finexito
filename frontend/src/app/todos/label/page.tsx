"use client";

import { useSearchParams } from "next/navigation";

import { useTodos } from "@/app/todos/shell";
import { TasksByProject } from "@/app/todos/tasks-by-project";
import { Pending } from "@/components/app/pending";
import { AppBar, Screen } from "@/components/app/frame";
import { useQuery } from "@/lib/api/client";

/** `?id=`: the label. */
export default function LabelPage() {
  const id = useSearchParams().get("id") ?? "";
  const label = useTodos().labels.find((l) => l.id === id);
  const { data: tasks, error } = useQuery("/api/v1/todos/tasks/", { params: { query: { label: id } } });
  if (!label) return <Screen>This label doesn&apos;t exist.</Screen>;
  return (
    <>
      <AppBar title={`#${label.name}`} back="/todos/filters" />
      <Screen>
        {tasks ? <TasksByProject tasks={tasks} empty="No open tasks with this label." /> : <Pending error={error} />}
      </Screen>
    </>
  );
}
