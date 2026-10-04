"use client";

import { Copy, LogOut, RefreshCw, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { inviteLink, leaveProject, removeCollaborator, transferProject } from "@/app/todos/actions";
import { useTodos, type Project } from "@/app/todos/shell";
import { Avatar } from "@/components/app/avatar";
import { List, ListRow } from "@/components/app/list";
import { ActionSheet, Sheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useQuery } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Person = components["schemas"]["Person"];

export { Avatar };

/** The people in a shared project, owner first; none for a project of one. */
export function usePeople(project: Pick<Project, "id" | "is_shared"> | undefined) {
  const { data } = useQuery(
    "/api/v1/todos/projects/{id}/collaborators/",
    project?.is_shared ? { params: { path: { id: project.id } } } : null,
  );
  return data ?? [];
}

/** Overlapping avatars, as in a shared project's header. */
export function Avatars({ people, max = 4 }: { people: Person[]; max?: number }) {
  return (
    <span className="flex -space-x-1.5">
      {people.slice(0, max).map((p) => (
        <Avatar key={p.id} person={p} className="ring-background ring-2" />
      ))}
      {people.length > max && (
        <span className="bg-muted ring-background inline-flex size-6 items-center justify-center rounded-full text-[10px] ring-2">
          +{people.length - max}
        </span>
      )}
    </span>
  );
}

/** Who's in a project. The owner shares it by link, removes people, or hands it on; anyone else can leave. */
export function ShareSheet({ project, ...props }: { project: Project; open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter();
  const { confirm } = useTodos();
  const people = usePeople({ id: project.id, is_shared: props.open });
  const { data: link, mutate } = useQuery(
    "/api/v1/todos/projects/{id}/invite-link/",
    props.open && project.is_owner ? { params: { path: { id: project.id } } } : null,
  );
  const [chosen, setChosen] = useState<Person | null>(null);
  const url = link?.token ? `${location.origin}/join?token=${link.token}` : null;

  async function change(how: "reset" | "off") {
    const { error } = await inviteLink(project.id, how);
    if (error) toast.error(error);
    mutate();
  }

  async function remove(person: Person) {
    if (!(await confirm(`Remove ${person.name} from “${project.name}”? Their tasks here are unassigned.`, "Remove"))) return;
    const { error } = await removeCollaborator(project.id, person.id);
    if (error) toast.error(error);
  }

  return (
    <Sheet {...props} title={`Share “${project.name}”`}>
      {project.is_owner && (
        <>
          {url ? (
            <div className="flex flex-col gap-2">
              <p className="text-muted-foreground text-sm">
                Copy this link and send it to the people you want to invite.
              </p>
              <div className="flex gap-2">
                <Input readOnly value={url} aria-label="Invite link" className="h-11 flex-1 text-sm" onFocus={(e) => e.target.select()} />
                <Button
                  size="lg"
                  className="h-11"
                  onClick={async () => {
                    await navigator.clipboard.writeText(url);
                    toast.success("Link copied");
                  }}
                >
                  <Copy /> Copy link
                </Button>
              </div>
              {link?.is_full && <p className="text-destructive text-sm">This project is full; the link won&apos;t let anyone else in.</p>}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Joining by link is off.</p>
          )}
          <List>
            <ListRow icon={<RefreshCw />} onClick={() => change("reset")}>
              {url ? "Reset link (the old one stops working)" : "Turn on link joining"}
            </ListRow>
            {url && (
              <ListRow icon={<X />} onClick={() => change("off")}>
                Turn off link joining
              </ListRow>
            )}
          </List>
        </>
      )}
      <List title="People">
        {people.length === 0 && <ListRow>Only you, so far.</ListRow>}
        {people.map((person, index) => (
          <ListRow
            key={person.id}
            icon={<Avatar person={person} />}
            detail={index === 0 ? "Owner" : undefined}
            onClick={project.is_owner && index > 0 ? () => setChosen(person) : undefined}
          >
            {person.name}
          </ListRow>
        ))}
      </List>
      {!project.is_owner && (
        <List>
          <ListRow
            icon={<LogOut />}
            destructive
            onClick={async () => {
              if (!(await confirm(`Leave “${project.name}”? You'll need a new invite to come back.`, "Leave"))) return;
              const { error } = await leaveProject(project.id);
              if (error) return toast.error(error);
              props.onOpenChange(false);
              router.push("/todos/browse");
            }}
          >
            Leave project
          </ListRow>
        </List>
      )}
      <ActionSheet
        open={!!chosen}
        onOpenChange={(open) => !open && setChosen(null)}
        title={chosen?.name}
        actions={[
          {
            label: "Make owner",
            onSelect: async () => {
              if (!chosen) return;
              if (!(await confirm(`Hand “${project.name}” to ${chosen.name}? You'll stay in it as a collaborator.`, "Make owner"))) return;
              const { error } = await transferProject(project.id, chosen.id);
              if (error) toast.error(error);
            },
          },
          { label: "Remove from project", destructive: true, onSelect: () => chosen && remove(chosen) },
        ]}
      />
    </Sheet>
  );
}
