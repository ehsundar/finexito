"use client";

import { useSearchParams } from "next/navigation";

import { Comments } from "@/app/todos/comments";
import { Pending } from "@/components/app/pending";
import { AppBar, Screen } from "@/components/app/frame";
import { useQuery } from "@/lib/api/client";

/** `?project=`: the project's own comments, or notes on a project of one. */
export default function ProjectCommentsPage() {
  const id = useSearchParams().get("project") ?? "";
  const { data: project, error } = useQuery("/api/v1/todos/projects/{id}/", { params: { path: { id } } });
  if (!project) return <Pending error={error} missing="This project doesn’t exist." />;
  return (
    <>
      <AppBar
        back={project.is_inbox ? "/todos" : `/todos/project?id=${project.id}`}
        title={<span className="truncate">{project.name}</span>}
      />
      <Screen>
        <Comments project={project} />
      </Screen>
    </>
  );
}
