"use client";

import { useSearchParams } from "next/navigation";

import { FavouriteButton } from "@/app/todos/favourite-button";
import { useTodos } from "@/app/todos/shell";
import { TasksByProject } from "@/app/todos/tasks-by-project";
import { AppBar, Screen } from "@/components/app/frame";
import { useQuery } from "@/lib/api/client";

/** `?slug=`: the filter. */
export default function FilterPage() {
  const slug = useSearchParams().get("slug") ?? "";
  const filter = useTodos().filters.find((f) => f.slug === slug);
  const { data: tasks } = useQuery("/api/v1/todos/tasks/", { params: { query: { filter: slug } } });
  if (!filter) return <Screen>This filter doesn&apos;t exist.</Screen>;
  return (
    <>
      <AppBar
        title={filter.name}
        back="/todos/filters"
        actions={<FavouriteButton slug={slug} on={filter.is_favourite} />}
      />
      <Screen>{tasks && <TasksByProject tasks={tasks} empty="No tasks here." />}</Screen>
    </>
  );
}
