"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { closeTask, reopenTask } from "@/app/todos/actions";
import { SectionTitle } from "@/app/todos/project-header";
import { useTodos, type Project, type Section, type Task } from "@/app/todos/shell";
import { sortTasks, TaskCheck, TaskMeta, withoutId } from "@/app/todos/task-list";
import { InlineMarkdown } from "@/components/markdown/inline";
import { Button } from "@/components/ui/button";

/**
 * One column per section, "(No section)" first, swiped through sideways.
 * Cards are top-level tasks; sub-tasks show as the card's count.
 */
export function Board({
  project,
  sections,
  tasks,
}: {
  project: Project;
  sections: Section[];
  tasks: Task[];
}) {
  const { quickAdd } = useTodos();
  const [hidden, setHidden] = useState(new Set<string>());
  const columns: { section: Section | null; tasks: Task[] }[] = [
    { section: null, tasks: [] },
    ...sections.map((section) => ({ section, tasks: [] as Task[] })),
  ];
  for (const task of tasks) {
    if (task.parent || hidden.has(task.id)) continue;
    columns.find((c) => (c.section?.id ?? null) === (task.section ?? null))?.tasks.push(task);
  }

  async function complete(task: Task) {
    setHidden((h) => new Set(h).add(task.id));
    const { error } = await closeTask(task.id);
    if (error) return toast.error(error);
    toast("Task completed", {
      duration: 8000,
      action: {
        label: "Undo",
        onClick: async () => {
          const undone = await reopenTask(task.id);
          if (undone.error) return toast.error(undone.error);
          setHidden((h) => withoutId(h, task.id));
        },
      },
    });
  }

  return (
    <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-px-4 px-4 pb-4">
      {columns.map(({ section, tasks }) => (
        <section
          key={section?.id ?? "none"}
          className="bg-muted/50 flex w-[85%] shrink-0 snap-start flex-col gap-2 rounded-xl p-2"
        >
          <div className="flex min-h-9 items-center px-1">
            {section ? (
              <SectionTitle section={section} />
            ) : (
              <h2 className="text-muted-foreground text-sm font-medium">(No section)</h2>
            )}
          </div>
          {sortTasks(tasks, project.sort).map((task) => (
            <article
              key={task.id}
              className="bg-card flex items-start gap-3 rounded-lg border p-3"
            >
              <TaskCheck task={task} onComplete={() => complete(task)} />
              <div className="min-w-0 flex-1">
                <Link href={`/todos/tasks/${task.id}`} className="block break-words">
                  <InlineMarkdown source={task.content} />
                </Link>
                <TaskMeta task={task} />
              </div>
            </article>
          ))}
          <Button
            variant="ghost"
            size="lg"
            className="text-muted-foreground justify-start"
            onClick={() => quickAdd({ project: project.id, section: section?.id })}
          >
            <Plus /> Add task
          </Button>
        </section>
      ))}
    </div>
  );
}
