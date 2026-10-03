"use client";

import { Inbox, LayoutList, Plus, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, use, useCallback, useState } from "react";
import { toast } from "sonner";

import { createProject } from "@/app/todos/actions";
import { QuickAdd, type Prefill } from "@/app/todos/quick-add";
import { AppFrame, Fab, Tab, TabBar } from "@/components/app/frame";
import { ActionSheet, PromptSheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";
import { useQuery } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Project = components["schemas"]["Project"];
export type Section = components["schemas"]["Section"];
export type Label = components["schemas"]["Label"];
export type Filter = components["schemas"]["Filter"];
export type Task = components["schemas"]["Task"];
export type Colour = components["schemas"]["ColourEnum"];

export const COLOURS: Colour[] = [
  "neutral",
  "red",
  "orange",
  "yellow",
  "green",
  "teal",
  "blue",
  "purple",
  "pink",
];

/** A colour name's theme variable (globals.css). */
export const colourVar = (colour: Colour | undefined) => `var(--tag-${colour ?? "neutral"})`;

type Todos = {
  projects: Project[];
  sections: Section[];
  labels: Label[];
  filters: Filter[];
  quickAdd: (prefill?: Prefill) => void;
  confirm: (message: string, action?: string) => Promise<boolean>;
};

const TodosContext = createContext<Todos | null>(null);

export function useTodos() {
  const todos = use(TodosContext);
  if (!todos) throw new Error("useTodos needs the todos shell.");
  return todos;
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { data: projects } = useQuery("/api/v1/todos/projects/");
  const { data: sections } = useQuery("/api/v1/todos/sections/");
  const { data: labels } = useQuery("/api/v1/todos/labels/");
  const { data: filters } = useQuery("/api/v1/todos/filters/");
  const pathname = usePathname();
  const params = useSearchParams();
  const [prefill, setPrefill] = useState<Prefill | null>(null);
  const [question, setQuestion] = useState<{
    message: string;
    action: string;
    answer: (yes: boolean) => void;
  } | null>(null);

  const quickAdd = useCallback((value?: Prefill) => setPrefill(value ?? {}), []);
  const confirm = useCallback(
    (message: string, action = "Delete") =>
      new Promise<boolean>((answer) => setQuestion({ message, action, answer })),
    [],
  );
  const answer = (yes: boolean) => {
    question?.answer(yes);
    setQuestion(null);
  };

  // Everything on screen needs these; SWR fetches them again when the window
  // regains focus, so the client catches up with other tabs and devices.
  if (!projects || !sections || !labels || !filters) return null;

  // On a project's screen, new tasks go to that project.
  const project = (pathname === "/todos/project" && params.get("id")) || undefined;

  return (
    <TodosContext value={{ projects, sections, labels, filters, quickAdd, confirm }}>
      <AppFrame>
        {children}
        <TabBar
          action={
            <Fab aria-label="Add task" onClick={() => quickAdd({ project })}>
              <Plus />
            </Fab>
          }
        >
          <Tab href="/todos" icon={<Inbox />} label="Inbox" />
          <Tab href="/todos/search" icon={<Search />} label="Search" />
          <Tab
            href="/todos/browse"
            icon={<LayoutList />}
            label="Browse"
            match={["/todos/project", "/todos/filter", "/todos/label"]}
          />
        </TabBar>
      </AppFrame>

      <QuickAdd prefill={prefill} onClose={() => setPrefill(null)} />
      <ActionSheet
        open={!!question}
        onOpenChange={(open) => !open && answer(false)}
        title="Are you sure?"
        description={question?.message}
        actions={[{ label: question?.action, destructive: true, onSelect: () => answer(true) }]}
      />
    </TodosContext>
  );
}

/** Adds a project and opens it. */
export function NewProject() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  return (
    <>
      <Button variant="ghost" size="icon-sm" aria-label="Add project" onClick={() => setOpen(true)}>
        <Plus />
      </Button>
      <PromptSheet
        open={open}
        onOpenChange={setOpen}
        title="Add project"
        placeholder="Name"
        maxLength={120}
        submit="Add"
        onSubmit={async (name) => {
          const { data, error } = await createProject({ name });
          if (error) toast.error(error);
          if (data) router.push(`/todos/project?id=${data.id}`);
          return !error;
        }}
      />
    </>
  );
}

export function Dot({ colour }: { colour?: Colour }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2.5 shrink-0 rounded-full"
      style={{ background: colourVar(colour) }}
    />
  );
}
