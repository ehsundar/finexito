import type { Metadata } from "next";

import { Shell } from "@/app/todos/shell";
import { sessionApi } from "@/lib/auth/current-user";

export const metadata: Metadata = { title: { default: "Todos", template: "%s · Todos" } };

export default async function TodosLayout({ children }: LayoutProps<"/todos">) {
  const api = await sessionApi();
  const [projects, sections, labels, filters] = await Promise.all([
    api.GET("/api/v1/todos/projects/"),
    api.GET("/api/v1/todos/sections/"),
    api.GET("/api/v1/todos/labels/"),
    api.GET("/api/v1/todos/filters/"),
  ]);
  return (
    <Shell
      projects={projects.data ?? []}
      sections={sections.data ?? []}
      labels={labels.data ?? []}
      filters={filters.data ?? []}
    >
      {children}
    </Shell>
  );
}
