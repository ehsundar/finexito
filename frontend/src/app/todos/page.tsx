import { ProjectView } from "@/app/todos/project-view";

export const metadata = { title: "Inbox" };

export default async function InboxPage({ searchParams }: PageProps<"/todos">) {
  const { completed } = await searchParams;
  return <ProjectView id="inbox" completed={!!completed} />;
}
