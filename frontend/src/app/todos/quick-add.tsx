"use client";

import { Hash } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { createLabel, createSection, createTask } from "@/app/todos/actions";
import { dueText, useParsedDue } from "@/app/todos/due";
import { Dot, useTodos, type Label, type Project, type Section } from "@/app/todos/shell";
import { List, ListRow } from "@/components/app/list";
import { Sheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** What quick add was opened from; what the line names wins over it. */
export type Prefill = {
  project?: string;
  section?: string;
  parent?: string;
  labels?: string[];
  /** A day, `2026-10-07`, unless the line names one. */
  due?: string;
};

type Kind = "text" | "project" | "section" | "label" | "priority" | "date";
type Segment = { text: string; kind: Kind; created?: boolean };

const NEW_LABEL = /^([\p{L}\p{N}_-]{1,60})(?=\s|$)/u;
const PRIORITY = /^p([1-4])(?=\s|$)/;

function longest(rest: string, names: string[]) {
  const lowered = rest.toLowerCase();
  let best: string | null = null;
  for (const name of names) {
    const n = name.length;
    const fits = lowered.startsWith(name.toLowerCase()) && (n === rest.length || /\s/.test(rest[n]));
    if (fits && (best === null || n > best.length)) best = name;
  }
  return best;
}

type Parsed = {
  parts: Segment[];
  project: Project | null;
  /** An existing section, or the name of one to create. */
  section: Section | string | null;
  /** Existing labels, or names of ones to create. */
  labels: (Label | string)[];
  priority: 1 | 2 | 3 | 4 | null;
  content: string;
};

/**
 * Reads one line of quick add. `#` takes the longest matching project name
 * (only the first project counts), else the longest label name, else one word
 * as a new label. `/` takes the longest section name in the chosen project,
 * else one word as a new section. `p1`–`p4` is the priority. `@` is plain text,
 * kept for mentioning people. A backslash keeps a token as text.
 */
function parse(
  text: string,
  projects: Project[],
  labels: Label[],
  sectionsOf: (project: Project | null) => Section[],
): Parsed {
  const scan = (sections: Section[]) => {
    const found: Parsed = { parts: [], project: null, section: null, labels: [], priority: null, content: "" };
    const push = (piece: string, kind: Kind, created = false) => {
      const last = found.parts.at(-1);
      if (kind === "text" && last?.kind === "text") last.text += piece;
      else found.parts.push({ text: piece, kind, created });
    };
    const addLabel = (label: Label | string) => {
      const key = (l: Label | string) => (typeof l === "string" ? l.toLowerCase() : l.id);
      if (!found.labels.some((l) => key(l) === key(label))) found.labels.push(label);
    };
    let i = 0;
    while (i < text.length) {
      const startsWord = i === 0 || /\s/.test(text[i - 1]);
      const char = text[i];
      const rest = text.slice(i + 1);
      if (startsWord && char === "\\" && "#/p".includes(rest[0] ?? " ")) {
        push(rest[0], "text");
        i += 2;
        continue;
      }
      if (startsWord && char === "#") {
        const projectName: string | null = found.project ? null : longest(rest, projects.map((p) => p.name));
        if (projectName !== null) {
          found.project = projects.find((p) => p.name === projectName) ?? null;
          push(char + rest.slice(0, projectName.length), "project");
          i += 1 + projectName.length;
          continue;
        }
        const labelName = longest(rest, labels.map((l) => l.name));
        const word = NEW_LABEL.exec(rest)?.[1];
        if (labelName !== null || word) {
          const length = labelName?.length ?? word!.length;
          addLabel(labels.find((l) => l.name === labelName) ?? word!);
          push(char + rest.slice(0, length), "label", labelName === null);
          i += 1 + length;
          continue;
        }
      }
      if (startsWord && char === "/") {
        const name = longest(rest, sections.map((s) => s.name));
        const word = /^\S+/.exec(rest)?.[0];
        if (name !== null || word) {
          const length = name?.length ?? word!.length;
          found.section ??= sections.find((s) => s.name === name) ?? word!;
          push(char + rest.slice(0, length), "section", name === null);
          i += 1 + length;
          continue;
        }
      }
      const priority = startsWord && char === "p" ? PRIORITY.exec(text.slice(i)) : null;
      if (priority) {
        found.priority ??= Number(priority[1]) as 1 | 2 | 3 | 4;
        push(priority[0], "priority");
        i += priority[0].length;
        continue;
      }
      push(char, "text");
      i += 1;
    }
    found.content = found.parts
      .filter((p) => p.kind === "text")
      .map((p) => p.text)
      .join("")
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");
    return found;
  };
  // Sections belong to the project, which the line itself may name.
  return scan(sectionsOf(scan([]).project));
}

/** Marks the text from `start` to `end` as the date. */
function markDate(parts: Segment[], [start, end]: number[]) {
  const marked: Segment[] = [];
  let at = 0;
  for (const part of parts) {
    const [from, to] = [at, at + part.text.length];
    at = to;
    if (part.kind !== "text" || to <= start || from >= end) {
      marked.push(part);
      continue;
    }
    const cut = (a: number, b: number) => part.text.slice(Math.max(a, from) - from, Math.min(b, to) - from);
    if (from < start) marked.push({ text: cut(from, start), kind: "text" });
    marked.push({ text: cut(start, end), kind: "date" });
    if (to > end) marked.push({ text: cut(end, to), kind: "text" });
  }
  return marked;
}

/** The `#` being typed at the caret, if any: where it starts and what follows it. */
function typingTag(text: string, caret: number) {
  const match = /(?:^|\s)#([^#\n]*)$/.exec(text.slice(0, caret));
  if (!match) return null;
  return { start: caret - match[1].length - 1, query: match[1] };
}

const STYLE: Record<Kind, string> = {
  text: "",
  project: "bg-accent rounded px-0.5",
  section: "bg-accent rounded px-0.5",
  label: "bg-secondary rounded px-0.5",
  priority: "rounded px-0.5 font-medium",
  date: "bg-accent rounded px-0.5",
};

/** Opens with a prefill, closes with none. */
export function QuickAdd({ prefill, onClose }: { prefill: Prefill | null; onClose: () => void }) {
  const { projects, sections, labels } = useTodos();
  const [text, setText] = useState("");
  const [caret, setCaret] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const prefilled =
    projects.find((p) => p.id === prefill?.project) ?? projects.find((p) => p.is_inbox) ?? null;
  // The server finds a date in the line; the rest is read here.
  const found = useParsedDue(text, true);
  const date = found?.due && found.match ? { due: found.due, match: found.match } : null;
  const sectionsOf = (project: Project | null) => sections.filter((s) => s.project === (project ?? prefilled)?.id);
  const parsed = parse(
    date ? text.slice(0, date.match[0]) + text.slice(date.match[1]) : text,
    projects,
    labels,
    sectionsOf,
  );
  // A backslash keeps a date as text, and goes.
  if (date) parsed.content = parsed.content.replace(/(^|\s)\\(?=\w)/g, "$1");
  const parts = date ? markDate(parse(text, projects, labels, sectionsOf).parts, date.match) : parsed.parts;
  const project = parsed.project ?? prefilled;

  // While a `#` is being typed: matching projects first, then labels.
  const tag = typingTag(text, caret);
  const needle = tag?.query.toLowerCase() ?? "";
  const matches = (name: string) => name.toLowerCase().startsWith(needle);
  const suggestions = tag
    ? [
        ...projects
          .filter((p) => !p.is_inbox && matches(p.name))
          .map((p) => ({ key: p.id, name: p.name, icon: <Dot colour={p.colour} /> })),
        ...labels.filter((l) => matches(l.name)).map((l) => ({ key: l.id, name: l.name, icon: <Hash /> })),
      ].slice(0, 6)
    : [];

  function pick(name: string) {
    if (!tag) return;
    const before = `${text.slice(0, tag.start)}#${name} `;
    setText(before + text.slice(caret).trimStart());
    setCaret(before.length);
    requestAnimationFrame(() => input.current?.setSelectionRange(before.length, before.length));
  }

  /** Makes the new labels and section first, then the task. */
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!parsed.content || !project) return;
    setBusy(true);
    const error = await save(project);
    setBusy(false);
    if (error) return toast.error(error);
    toast.success("Task added");
    setText("");
  }

  async function save(project: Project) {
    const labelIds = [...(prefill?.labels ?? [])];
    for (const label of parsed.labels) {
      if (typeof label !== "string") labelIds.push(label.id);
      else {
        const { data, error } = await createLabel(label);
        if (error || !data) return error ?? "Could not add the label.";
        labelIds.push(data.id);
      }
    }
    let section = parsed.project ? null : (prefill?.section ?? null);
    if (typeof parsed.section === "string") {
      const { data, error } = await createSection(project.id, parsed.section);
      if (error || !data) return error ?? "Could not add the section.";
      section = data.id;
    } else if (parsed.section) section = parsed.section.id;
    const { error } = await createTask({
      project: project.id,
      section,
      // A project or section named in the line moves the task out from under its parent.
      parent: parsed.project || parsed.section ? null : (prefill?.parent ?? null),
      content: parsed.content,
      priority: parsed.priority ?? undefined,
      labels: [...new Set(labelIds)],
      ...(date ? { due_string: date.due.string } : prefill?.due ? { due_date: prefill.due } : {}),
    });
    return error;
  }

  return (
    <Sheet open={!!prefill} onOpenChange={(open) => !open && onClose()} title={`Add to ${project?.name ?? "Inbox"}`}>
      {/* What changes while typing sits above the input, so the input stays put. */}
      <form onSubmit={submit} className="flex flex-col gap-3">
        {suggestions.length > 0 && (
          // Tapping a suggestion keeps the keyboard up: the input never loses focus.
          <div onPointerDown={(event) => event.preventDefault()}>
            <List>
              {suggestions.map((s) => (
                <ListRow key={s.key} icon={s.icon} onClick={() => pick(s.name)}>
                  {s.name}
                </ListRow>
              ))}
            </List>
          </div>
        )}
        <p
          id="quick-add-preview"
          className="text-muted-foreground min-h-5 text-sm break-words whitespace-pre-wrap"
        >
          {text ? (
            parts.map((part, index) => (
              <span
                key={index}
                title={part.created ? `New ${part.kind}` : undefined}
                className={cn(STYLE[part.kind], part.created && "underline decoration-dashed")}
                style={
                  part.kind === "priority"
                    ? { color: `var(--priority-${part.text.slice(1)})` }
                    : part.kind === "text"
                      ? undefined
                      : { color: "var(--foreground)" }
                }
              >
                {part.text}
              </span>
            ))
          ) : (
            <>Type # for a project or label, / for a section, p1 for priority, or a date.</>
          )}
          {(date || prefill?.due) && (
            <span className="block">
              {date
                ? date.due.date
                  ? `Due ${dueText(date.due.date, date.due.time)}${date.due.is_recurring ? ", repeating" : ""}`
                  : "No date"
                : `Due ${dueText(prefill!.due!)}`}
            </span>
          )}
        </p>
        <Input
          value={text}
          ref={input}
          onChange={(event) => {
            setText(event.target.value);
            setCaret(event.target.selectionStart ?? event.target.value.length);
          }}
          onSelect={(event) => setCaret(event.currentTarget.selectionStart ?? 0)}
          placeholder="Task name"
          maxLength={1000}
          autoFocus
          enterKeyHint="send"
          aria-describedby="quick-add-preview"
          className="h-11 text-base"
        />
        <Button type="submit" size="lg" className="h-11" disabled={busy || !parsed.content}>
          Add task
        </Button>
      </form>
    </Sheet>
  );
}
