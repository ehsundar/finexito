"use client";

import Link from "next/link";
import { toast } from "sonner";

import { reopenTask } from "@/app/todos/actions";
import type { Task } from "@/app/todos/shell";
import { TaskCheck } from "@/app/todos/task-list";
import { InlineMarkdown } from "@/components/markdown/inline";

/** Completed tasks, newest first; ticking one reopens it. */
export function CompletedList({ tasks }: { tasks: Task[] }) {
  return (
    <section>
      <h2 className="text-muted-foreground flex min-h-10 items-center border-b text-sm font-medium">Completed</h2>
      {tasks.length === 0 && <p className="text-muted-foreground py-3 text-sm">Nothing completed yet.</p>}
      <ul>
        {tasks.map((task) => (
          <li key={task.id} className="flex items-start gap-3 border-b py-3">
            <TaskCheck
              task={task}
              onComplete={async () => {
                const { error } = await reopenTask(task.id);
                if (error) toast.error(error);
              }}
            />
            <Link href={`/todos/task?id=${task.id}`} className="text-muted-foreground min-w-0 flex-1 line-through">
              <InlineMarkdown source={task.content} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
