"use client";

import { Ellipsis, LayoutGrid, List as ListIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import {
  createSection,
  deleteProject,
  deleteSection,
  downloadCsv,
  saveTemplate,
  updateProject,
  updateSection,
} from "@/app/todos/actions";
import { Avatars, ShareSheet, usePeople } from "@/app/todos/people";
import { COLOURS, Dot, useTodos, type Project, type Section } from "@/app/todos/shell";
import { AppBar } from "@/components/app/frame";
import { ActionSheet, PromptSheet, type Action } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";

const SORTS = { manual: "Manual", priority: "Priority", name: "Name", added: "Date added" } as const;

async function report(result: Promise<{ error?: string }>) {
  const { error } = await result;
  if (error) toast.error(error);
  return !error;
}

type Sheet = "menu" | "sort" | "colour" | "parent" | "rename" | "section" | "share" | null;

/** A project's top bar, with the list/board switch and its menu. */
export function ProjectHeader({ project, showingCompleted }: { project: Project; showingCompleted: boolean }) {
  const router = useRouter();
  const { projects, confirm } = useTodos();
  const [sheet, setSheet] = useState<Sheet>(null);
  const people = usePeople(project);
  const update = (body: Parameters<typeof updateProject>[1]) => report(updateProject(project.id, body));
  const here = project.is_inbox ? "/todos" : `/todos/project?id=${project.id}`;
  const close = (open: boolean) => !open && setSheet(null);
  // A sheet picked from the menu opens once the menu has closed.
  const then = (next: Sheet) => () => setTimeout(() => setSheet(next));

  const menu: Action[] = [
    { label: "Add section", onSelect: then("section") },
    { label: "Sort by", onSelect: then("sort") },
    {
      label: showingCompleted ? "Hide completed" : "Show completed",
      onSelect: () => router.push(showingCompleted ? here : `${here}${project.is_inbox ? "?" : "&"}completed=1`),
    },
  ];
  menu.push(
    { label: "Comments", onSelect: () => router.push(`/todos/comments?project=${project.id}`) },
    { label: "Add from a template", onSelect: () => router.push("/todos/templates") },
    {
      label: "Save as template",
      onSelect: async () => {
        if (await report(saveTemplate(project.id))) toast.success("Saved; find it in Templates");
      },
    },
    { label: "Download CSV", onSelect: () => report(downloadCsv("projects", project.id)) },
  );
  if (!project.is_inbox) {
    menu.push({ label: project.is_owner ? "Share" : "People", onSelect: then("share") });
  }
  if (!project.is_inbox && !project.is_owner) {
    // A collaborator's own place for the project; the rest is the owner's.
    menu.push(
      { label: "Colour", onSelect: then("colour") },
      { label: "Move under", onSelect: then("parent") },
      {
        label: project.is_favourite ? "Remove from favourites" : "Add to favourites",
        onSelect: () => update({ is_favourite: !project.is_favourite }),
      },
    );
  }
  if (!project.is_inbox && project.is_owner) {
    menu.push(
      { label: "Rename", onSelect: then("rename") },
      { label: "Colour", onSelect: then("colour") },
      { label: "Move under", onSelect: then("parent") },
      {
        label: project.is_favourite ? "Remove from favourites" : "Add to favourites",
        onSelect: () => update({ is_favourite: !project.is_favourite }),
      },
      {
        label: project.is_archived ? "Unarchive" : "Archive",
        onSelect: () => update({ is_archived: !project.is_archived }),
      },
      {
        label: "Delete",
        destructive: true,
        onSelect: async () => {
          const sure = await confirm(`Delete “${project.name}” with its sub-projects, sections and tasks?`);
          if (sure && (await report(deleteProject(project.id)))) router.push("/todos/browse");
        },
      },
    );
  }

  return (
    <>
      <AppBar
        back={project.is_inbox ? undefined : "/todos/browse"}
        title={
          <>
            {!project.is_inbox && <Dot colour={project.colour} />}
            <span className="truncate">{project.name}</span>
            {project.is_archived && <span className="text-muted-foreground text-sm font-normal">Archived</span>}
          </>
        }
        actions={
          <>
            {people.length > 0 && (
              <button type="button" aria-label="People" className="px-1" onClick={() => setSheet("share")}>
                <Avatars people={people} max={3} />
              </button>
            )}
            <Button
              variant="ghost"
              size="icon-lg"
              aria-label={project.view === "board" ? "Show as list" : "Show as board"}
              onClick={() => update({ view: project.view === "board" ? "list" : "board" })}
            >
              {project.view === "board" ? <ListIcon /> : <LayoutGrid />}
            </Button>
            <Button variant="ghost" size="icon-lg" aria-label="Project menu" onClick={() => setSheet("menu")}>
              <Ellipsis />
            </Button>
          </>
        }
      />

      <ActionSheet open={sheet === "menu"} onOpenChange={close} title={project.name} actions={menu} />
      <ActionSheet
        open={sheet === "sort"}
        onOpenChange={close}
        title="Sort by"
        actions={Object.entries(SORTS).map(([sort, label]) => ({
          label,
          checked: (project.sort ?? "manual") === sort,
          onSelect: () => update({ sort: sort as keyof typeof SORTS }),
        }))}
      />
      <ActionSheet
        open={sheet === "colour"}
        onOpenChange={close}
        title="Colour"
        actions={COLOURS.map((colour) => ({
          label: <span className="capitalize">{colour}</span>,
          icon: <Dot colour={colour} />,
          checked: project.colour === colour,
          onSelect: () => update({ colour }),
        }))}
      />
      <ActionSheet
        open={sheet === "parent"}
        onOpenChange={close}
        title="Move under"
        actions={[
          { label: "Top level", checked: !project.parent, onSelect: () => update({ parent: null }) },
          ...projects
            // Only your own projects: a shared one goes under them, not theirs.
            .filter((p) => p.id !== project.id && !p.is_inbox && p.is_owner)
            .map((p) => ({
              label: p.name,
              icon: <Dot colour={p.colour} />,
              checked: project.parent === p.id,
              onSelect: () => update({ parent: p.id }),
            })),
        ]}
      />
      <PromptSheet
        open={sheet === "rename"}
        onOpenChange={close}
        title="Rename project"
        initial={project.name}
        maxLength={120}
        onSubmit={(name) => update({ name })}
      />
      {!project.is_inbox && <ShareSheet project={project} open={sheet === "share"} onOpenChange={close} />}
      <PromptSheet
        open={sheet === "section"}
        onOpenChange={close}
        title="Add section"
        placeholder="Name"
        maxLength={500}
        submit="Add"
        onSubmit={(name) => report(createSection(project.id, name))}
      />
    </>
  );
}

export function SectionTitle({ section }: { section: Section }) {
  const { projects, confirm } = useTodos();
  const [sheet, setSheet] = useState<"menu" | "move" | "rename" | null>(null);
  const close = (open: boolean) => !open && setSheet(null);
  return (
    <div className="flex flex-1 items-center gap-2">
      <h2 className="flex-1 text-sm font-semibold">{section.name}</h2>
      <Button variant="ghost" size="icon-sm" aria-label="Section menu" onClick={() => setSheet("menu")}>
        <Ellipsis />
      </Button>
      <ActionSheet
        open={sheet === "menu"}
        onOpenChange={close}
        title={section.name}
        actions={[
          { label: "Rename", onSelect: () => setTimeout(() => setSheet("rename")) },
          // Only the owner moves sections out of a shared project.
          ...(projects.find((p) => p.id === section.project)?.is_owner === false
            ? []
            : [{ label: "Move to", onSelect: () => setTimeout(() => setSheet("move")) }]),
          { label: "Archive", onSelect: () => report(updateSection(section.id, { is_archived: true })) },
          {
            label: "Delete",
            destructive: true,
            onSelect: async () => {
              if (await confirm(`Delete the section “${section.name}” with its tasks?`))
                report(deleteSection(section.id));
            },
          },
        ]}
      />
      <ActionSheet
        open={sheet === "move"}
        onOpenChange={close}
        title="Move to"
        actions={projects
          .filter((p) => p.id !== section.project)
          .map((p) => ({
            label: p.name,
            icon: <Dot colour={p.colour} />,
            onSelect: () => report(updateSection(section.id, { project: p.id })),
          }))}
      />
      <PromptSheet
        open={sheet === "rename"}
        onOpenChange={close}
        title="Rename section"
        initial={section.name}
        maxLength={500}
        onSubmit={(name) => report(updateSection(section.id, { name }))}
      />
    </div>
  );
}
