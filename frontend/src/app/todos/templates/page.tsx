"use client";

import { LayoutTemplate, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import {
  applyTemplate,
  deleteTemplate,
  downloadCsv,
  importTemplate,
  renameTemplate,
} from "@/app/todos/actions";
import { Dot, useTodos } from "@/app/todos/shell";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";
import { ActionSheet, PromptSheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";
import { useQuery } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Template = components["schemas"]["Template"];

/** Built-in templates by category, then the member's own; each starts a project or adds to one. */
export default function TemplatesPage() {
  const router = useRouter();
  const { projects, confirm } = useTodos();
  const { data: templates = [] } = useQuery("/api/v1/todos/templates/");
  const [chosen, setChosen] = useState<Template | null>(null);
  const [sheet, setSheet] = useState<"menu" | "into" | "rename" | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const categories = [...new Set(templates.map((t) => t.category))];
  const close = (open: boolean) => !open && setSheet(null);

  async function start(template: Template, project?: string) {
    const { data, error } = await applyTemplate(template.id, project ? { project } : {});
    if (error) return toast.error(error);
    toast.success(project ? "Added from the template" : "Project created");
    if (data) router.push(data.is_inbox ? "/todos" : `/todos/project?id=${data.id}`);
  }

  return (
    <>
      <AppBar
        back="/todos/browse"
        title="Templates"
        actions={
          <Button variant="ghost" size="icon-lg" aria-label="Import a CSV file" onClick={() => picker.current?.click()}>
            <Upload />
          </Button>
        }
      />
      <input
        ref={picker}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={async (event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          const { error } = await importTemplate(file);
          if (error) toast.error(error);
          else toast.success("Template imported");
        }}
      />
      <Screen>
        {categories.map((category) => (
          <List key={category} title={category}>
            {templates
              .filter((t) => t.category === category)
              .map((t) => (
                <ListRow
                  key={t.id}
                  icon={<LayoutTemplate />}
                  detail={`${t.task_count} tasks`}
                  onClick={() => {
                    setChosen(t);
                    setSheet("menu");
                  }}
                >
                  <span className="block truncate">{t.name}</span>
                  {t.description && (
                    <span className="text-muted-foreground block truncate text-xs">{t.description}</span>
                  )}
                </ListRow>
              ))}
          </List>
        ))}
        {!templates.some((t) => t.is_mine) && (
          <p className="text-muted-foreground px-4 text-sm">
            Save any of your projects as a template from its menu, or import a CSV file.
          </p>
        )}
      </Screen>
      <ActionSheet
        open={sheet === "menu"}
        onOpenChange={close}
        title={chosen?.name}
        description={chosen?.description}
        actions={[
          { label: "Start a project", onSelect: () => chosen && start(chosen) },
          { label: "Add to a project", onSelect: () => setTimeout(() => setSheet("into")) },
          {
            label: "Download CSV",
            onSelect: async () => {
              const { error } = chosen ? await downloadCsv("templates", chosen.id) : {};
              if (error) toast.error(error);
            },
          },
          ...(chosen?.is_mine
            ? [
                { label: "Rename", onSelect: () => setTimeout(() => setSheet("rename")) },
                {
                  label: "Delete",
                  destructive: true,
                  onSelect: async () => {
                    if (!chosen || !(await confirm(`Delete the template “${chosen.name}”?`))) return;
                    const { error } = await deleteTemplate(chosen.id);
                    if (error) toast.error(error);
                  },
                },
              ]
            : []),
        ]}
      />
      <ActionSheet
        open={sheet === "into"}
        onOpenChange={close}
        title="Add to"
        actions={projects.map((p) => ({
          label: p.name,
          icon: <Dot colour={p.colour} />,
          onSelect: () => chosen && start(chosen, p.id),
        }))}
      />
      <PromptSheet
        open={sheet === "rename"}
        onOpenChange={close}
        title="Rename template"
        initial={chosen?.name}
        maxLength={120}
        onSubmit={async (name) => {
          const { error } = chosen ? await renameTemplate(chosen.id, name) : {};
          if (error) toast.error(error);
          return !error;
        }}
      />
    </>
  );
}
