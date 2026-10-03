import { ProjectView } from "@/app/todos/project-view";

export default async function ProjectPage({ params, searchParams }: PageProps<"/todos/projects/[id]">) {
  const [{ id }, { completed }] = await Promise.all([params, searchParams]);
  return <ProjectView id={id} completed={!!completed} />;
}
