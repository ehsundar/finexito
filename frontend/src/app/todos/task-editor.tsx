"use client";

import { Bell, CalendarDays, Check, Flag, Folder, Tag, Trash2, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { closeTask, createLabel, deleteTask, reopenTask, updateTask } from "@/app/todos/actions";
import { DueLabel, DueSheet } from "@/app/todos/due";
import { Avatar, usePeople } from "@/app/todos/people";
import { reminderText, RemindersSheet, useReminders } from "@/app/todos/reminders";
import { colourVar, Dot, useTodos, type Task } from "@/app/todos/shell";
import { priorityVar, TaskCheck, withoutId } from "@/app/todos/task-list";
import { List, ListRow } from "@/components/app/list";
import { ActionSheet, Sheet } from "@/components/app/sheet";
import { MarkdownEditor } from "@/components/markdown/editor";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const PRIORITIES = [1, 2, 3, 4] as const;

/** One task's screen: its title, description, priority, labels and place. */
export function TaskEditor({ task, description }: { task: Task; description: React.ReactNode }) {
  const router = useRouter();
  const { projects, sections, labels, confirm } = useTodos();
  const [editing, setEditing] = useState(false);
  const [sheet, setSheet] = useState<"move" | "labels" | "priority" | "due" | "reminders" | "assignee" | null>(null);
  const { data: reminders = [] } = useReminders(task);
  const project = projects.find((p) => p.id === task.project);
  const section = sections.find((s) => s.id === task.section);
  const people = usePeople(project);
  const assignee = people.find((p) => p.id === task.assignee);
  const own = labels.filter((l) => task.labels?.includes(l.id));
  const close = (open: boolean) => !open && setSheet(null);

  async function save(body: Parameters<typeof updateTask>[1]) {
    const { error } = await updateTask(task.id, body);
    if (error) toast.error(error);
    return !error;
  }

  return (
    <article className="flex flex-col gap-6">
      <div className="flex items-start gap-3">
        <span className="pt-2">
          <TaskCheck
            task={task}
            onComplete={async () => {
              const { error } = await (task.completed_at ? reopenTask(task.id) : closeTask(task.id));
              if (error) toast.error(error);
            }}
          />
        </span>
        <textarea
          key={task.content}
          defaultValue={task.content}
          maxLength={500}
          rows={1}
          aria-label="Task name"
          className={cn(
            "field-sizing-content min-w-0 flex-1 resize-none bg-transparent py-1 text-xl font-medium outline-none",
            task.completed_at && "text-muted-foreground line-through",
          )}
          onBlur={(event) => {
            const content = event.target.value.trim();
            if (content && content !== task.content) save({ content });
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            }
          }}
        />
      </div>

      <button type="button" onClick={() => setEditing(true)} className="active:bg-accent -mx-2 rounded-lg p-2 text-left">
        {description ?? <span className="text-muted-foreground">Add a description</span>}
      </button>
      <MarkdownEditor
        open={editing}
        onOpenChange={setEditing}
        title="Description"
        initial={task.description ?? ""}
        placeholder="Add details, a checklist or links"
        maxLength={16000}
        onSave={(description) => save({ description })}
      />

      <List>
        <ListRow
          icon={<CalendarDays />}
          onClick={() => setSheet("due")}
          detail={task.due_date ? <DueLabel task={task} /> : "None"}
        >
          Due date
        </ListRow>
        <ListRow
          icon={<Bell />}
          onClick={() => setSheet("reminders")}
          detail={
            reminders.length > 1
              ? `${reminders.length} reminders`
              : reminders.length
                ? reminderText(reminders[0])
                : "None"
          }
        >
          Reminders
        </ListRow>
        {people.length > 0 && (
          <ListRow
            icon={<UserRound />}
            onClick={() => setSheet("assignee")}
            detail={
              assignee ? (
                <span className="flex items-center gap-1.5">
                  <Avatar person={assignee} className="size-5" />
                  {assignee.name}
                </span>
              ) : (
                "No one"
              )
            }
          >
            Assignee
          </ListRow>
        )}
        <ListRow
          icon={<Folder />}
          onClick={() => setSheet("move")}
          detail={
            <span className="flex items-center gap-1.5">
              <Dot colour={project?.colour} />
              {project?.name}
              {section && ` / ${section.name}`}
            </span>
          }
        >
          Project
        </ListRow>
        <ListRow
          icon={<Flag style={{ color: priorityVar(task.priority) }} />}
          onClick={() => setSheet("priority")}
          detail={`Priority ${task.priority ?? 4}`}
        >
          Priority
        </ListRow>
        <ListRow
          icon={<Tag />}
          onClick={() => setSheet("labels")}
          detail={
            own.length
              ? own.map((l) => (
                  <span key={l.id} className="ml-1.5" style={{ color: colourVar(l.colour) }}>
                    #{l.name}
                  </span>
                ))
              : "None"
          }
        >
          Labels
        </ListRow>
      </List>

      <List>
        <ListRow
          icon={<Trash2 />}
          destructive
          onClick={async () => {
            const subtasks = task.subtask_count ? ` and its ${task.subtask_count} sub-tasks` : "";
            if (!(await confirm(`Delete “${task.content}”${subtasks}?`))) return;
            const { error } = await deleteTask(task.id);
            if (error) return toast.error(error);
            router.push(project?.is_inbox ? "/todos" : `/todos/project?id=${task.project}`);
          }}
        >
          Delete task
        </ListRow>
      </List>

      <ActionSheet
        open={sheet === "priority"}
        onOpenChange={close}
        title="Priority"
        actions={PRIORITIES.map((priority) => ({
          label: `Priority ${priority}`,
          icon: <Flag style={{ color: priorityVar(priority) }} />,
          checked: (task.priority ?? 4) === priority,
          onSelect: () => save({ priority }),
        }))}
      />
      <ActionSheet
        open={sheet === "assignee"}
        onOpenChange={close}
        title="Assign to"
        actions={[
          { label: "No one", checked: !task.assignee, onSelect: () => save({ assignee: null }) },
          ...people.map((person) => ({
            label: person.name,
            icon: <Avatar person={person} className="size-5" />,
            checked: task.assignee === person.id,
            onSelect: () => save({ assignee: person.id }),
          })),
        ]}
      />
      <DueSheet task={task} open={sheet === "due"} onOpenChange={close} />
      <RemindersSheet task={task} open={sheet === "reminders"} onOpenChange={close} />
      <MoveSheet task={task} open={sheet === "move"} onOpenChange={close} />
      <LabelSheet task={task} open={sheet === "labels"} onOpenChange={close} />
    </article>
  );
}

/** Moves a task to another project, or a section in one. */
function MoveSheet({ task, ...props }: { task: Task; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { projects, sections } = useTodos();
  const [q, setQ] = useState("");
  // Only the owner moves tasks out of a shared project.
  const here = projects.find((p) => p.id === task.project);
  const targets = here?.is_owner === false ? [here] : projects;
  const options = targets.flatMap((p) => [
    { project: p, section: null as null | (typeof sections)[number] },
    ...sections.filter((s) => s.project === p.id).map((s) => ({ project: p, section: s })),
  ]);
  const shown = options.filter(({ project, section }) =>
    `${project.name} ${section?.name ?? ""}`.toLowerCase().includes(q.toLowerCase()),
  );

  async function pick(project: string, section: string | null) {
    props.onOpenChange(false);
    const { error } = await updateTask(task.id, { project, section });
    if (error) toast.error(error);
  }

  return (
    <Sheet {...props} title="Move to">
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Project or section" type="search" enterKeyHint="search" className="h-11 text-base" />
      <List>
        {shown.map(({ project, section }) => (
          <ListRow
            key={`${project.id}-${section?.id ?? ""}`}
            icon={section ? <span /> : <Dot colour={project.colour} />}
            indent={section ? 1 : 0}
            detail={
              task.project === project.id && (task.section ?? null) === (section?.id ?? null) ? (
                <Check className="text-primary size-4" />
              ) : undefined
            }
            onClick={() => pick(project.id, section?.id ?? null)}
          >
            {section ? section.name : project.name}
          </ListRow>
        ))}
      </List>
    </Sheet>
  );
}

/** Ticks a task's labels, or makes a new one. */
function LabelSheet({ task, ...props }: { task: Task; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { labels } = useTodos();
  const [chosen, setChosen] = useState(new Set(task.labels ?? []));
  const [q, setQ] = useState("");
  const shown = labels.filter((l) => l.name.toLowerCase().includes(q.toLowerCase()));
  const exact = labels.some((l) => l.name.toLowerCase() === q.trim().toLowerCase());

  async function save(ids: Set<string>) {
    setChosen(ids);
    const { error } = await updateTask(task.id, { labels: [...ids] });
    if (error) toast.error(error);
  }

  async function create() {
    const { data, error } = await createLabel(q.trim());
    if (error || !data) return toast.error(error ?? "Could not add the label.");
    setQ("");
    await save(new Set(chosen).add(data.id));
  }

  return (
    <Sheet {...props} title="Labels">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (q.trim() && !exact) create();
        }}
      >
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find or add a label" enterKeyHint="done" className="h-11 text-base" />
      </form>
      <List>
        {shown.map((l) => (
          <ListRow
            key={l.id}
            icon={<Tag style={{ color: colourVar(l.colour) }} />}
            detail={chosen.has(l.id) ? <Check className="text-primary size-4" /> : undefined}
            onClick={() => save(chosen.has(l.id) ? withoutId(chosen, l.id) : new Set(chosen).add(l.id))}
          >
            {l.name}
          </ListRow>
        ))}
        {q.trim() && !exact && <ListRow onClick={create}>Add label “{q.trim()}”</ListRow>}
      </List>
    </Sheet>
  );
}
