import { notFound } from "next/navigation";

import { FavouriteButton } from "@/app/todos/favourite-button";
import { TasksByProject } from "@/app/todos/tasks-by-project";
import { AppBar, Screen } from "@/components/app/frame";
import { sessionApi } from "@/lib/auth/current-user";

export default async function FilterPage({ params }: PageProps<"/todos/filters/[slug]">) {
  const { slug } = await params;
  const api = await sessionApi();
  const [{ data: filters = [] }, { data: tasks }] = await Promise.all([
    api.GET("/api/v1/todos/filters/"),
    api.GET("/api/v1/todos/tasks/", { params: { query: { filter: slug } } }),
  ]);
  const filter = filters.find((f) => f.slug === slug);
  if (!filter || !tasks) notFound();
  return (
    <>
      <AppBar
        title={filter.name}
        back="/todos/filters"
        actions={<FavouriteButton slug={slug} on={filter.is_favourite} />}
      />
      <Screen>
        <TasksByProject tasks={tasks} empty="No tasks here." />
      </Screen>
    </>
  );
}
