import { notFound } from "next/navigation";

import { TasksByProject } from "@/app/todos/tasks-by-project";
import { AppBar, Screen } from "@/components/app/frame";
import { sessionApi } from "@/lib/auth/current-user";

export default async function LabelPage({ params }: PageProps<"/todos/labels/[id]">) {
  const { id } = await params;
  const api = await sessionApi();
  const [{ data: label }, { data: tasks }] = await Promise.all([
    api.GET("/api/v1/todos/labels/{id}/", { params: { path: { id } } }),
    api.GET("/api/v1/todos/tasks/", { params: { query: { label: id } } }),
  ]);
  if (!label || !tasks) notFound();
  return (
    <>
      <AppBar title={`#${label.name}`} back="/todos/filters" />
      <Screen>
        <TasksByProject tasks={tasks} empty="No open tasks with this label." />
      </Screen>
    </>
  );
}
