"use client";

import { Ellipsis, Hash, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { createLabel, deleteLabel, updateLabel } from "@/app/todos/actions";
import { COLOURS, colourVar, Dot, useTodos, type Label } from "@/app/todos/shell";
import { List, ListRow } from "@/components/app/list";
import { ActionSheet, PromptSheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";

async function report(result: Promise<{ error?: string }>) {
  const { error } = await result;
  if (error) toast.error(error);
  return !error;
}

/** The member's labels, with adding, renaming, colours, favourites and deleting. */
export function LabelRows({ labels }: { labels: Label[] }) {
  const { confirm } = useTodos();
  const [label, setLabel] = useState<Label | null>(null);
  const [sheet, setSheet] = useState<"menu" | "colour" | "name" | null>(null);
  const close = (open: boolean) => !open && setSheet(null);
  const open = (next: typeof sheet, of: Label | null) => {
    setLabel(of);
    setSheet(next);
  };

  return (
    <>
      <List
        title="Labels"
        action={
          <Button variant="ghost" size="icon-sm" aria-label="Add label" onClick={() => open("name", null)}>
            <Plus />
          </Button>
        }
      >
        {labels.map((l) => (
          <ListRow
            key={l.id}
            href={`/todos/label?id=${l.id}`}
            icon={<Hash style={{ color: colourVar(l.colour) }} />}
            detail={l.open_task_count || undefined}
            trailing={
              <Button variant="ghost" size="icon-lg" aria-label="Label menu" onClick={() => open("menu", l)}>
                <Ellipsis />
              </Button>
            }
          >
            {l.name}
          </ListRow>
        ))}
        {labels.length === 0 && <ListRow>No labels yet.</ListRow>}
      </List>

      {label && (
        <>
          <ActionSheet
            open={sheet === "menu"}
            onOpenChange={close}
            title={`#${label.name}`}
            actions={[
              { label: "Rename", onSelect: () => setTimeout(() => setSheet("name")) },
              { label: "Colour", onSelect: () => setTimeout(() => setSheet("colour")) },
              {
                label: label.is_favourite ? "Remove from favourites" : "Add to favourites",
                onSelect: () => report(updateLabel(label.id, { is_favourite: !label.is_favourite })),
              },
              {
                label: "Delete",
                destructive: true,
                onSelect: async () => {
                  if (await confirm(`Delete #${label.name}? Its tasks stay; they lose the label.`))
                    report(deleteLabel(label.id));
                },
              },
            ]}
          />
          <ActionSheet
            open={sheet === "colour"}
            onOpenChange={close}
            title="Colour"
            actions={COLOURS.map((colour) => ({
              label: <span className="capitalize">{colour}</span>,
              icon: <Dot colour={colour} />,
              checked: label.colour === colour,
              onSelect: () => report(updateLabel(label.id, { colour })),
            }))}
          />
        </>
      )}
      <PromptSheet
        key={label?.id ?? "new"}
        open={sheet === "name"}
        onOpenChange={close}
        title={label ? "Rename label" : "Add label"}
        initial={label?.name}
        placeholder="Name"
        maxLength={60}
        submit={label ? "Save" : "Add"}
        onSubmit={(name) => report(label ? updateLabel(label.id, { name }) : createLabel(name))}
      />
    </>
  );
}
