"use client";

import { Check } from "lucide-react";
import { toast } from "sonner";

import { Dot, useTodos } from "@/app/todos/shell";
import { List, ListRow } from "@/components/app/list";
import { Sheet } from "@/components/app/sheet";
import { Button } from "@/components/ui/button";
import { api, errorMessage, revalidate, useQuery } from "@/lib/api/client";

/** The member's Google Calendar connection; nothing where the deployment has none. */
export function useGoogleCalendar() {
  return useQuery("/api/v1/todos/google/");
}

/** Connect, choose which projects the calendar shows, or disconnect. */
export function GoogleCalendarSheet(props: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { projects, confirm } = useTodos();
  const { data: google } = useGoogleCalendar();
  const own = projects.filter((p) => p.is_owner);
  const chosen = google?.projects ? new Set(google.projects) : null;

  async function choose(projects: string[] | null) {
    const { error } = await api.PATCH("/api/v1/todos/google/", { body: { projects } });
    if (error) toast.error(errorMessage(error));
    revalidate();
  }

  async function connect() {
    const { data, error } = await api.GET("/api/v1/todos/google/connect/");
    if (error || !data) return toast.error(errorMessage(error));
    location.assign(data.url);
  }

  return (
    <Sheet
      {...props}
      title="Google Calendar"
      description="Your dated tasks in a calendar of their own; moving them there moves them here."
    >
      {google?.status === "connected" ? (
        <>
          <List title="Show tasks from">
            <ListRow onClick={() => choose(null)} detail={!chosen ? <Check className="text-primary size-4" /> : undefined}>
              All my projects
            </ListRow>
            {own.map((p) => (
              <ListRow
                key={p.id}
                icon={<Dot colour={p.colour} />}
                detail={chosen?.has(p.id) ? <Check className="text-primary size-4" /> : undefined}
                onClick={() => {
                  const next = new Set(chosen ?? []);
                  if (next.has(p.id)) next.delete(p.id);
                  else next.add(p.id);
                  choose([...next]);
                }}
              >
                {p.name}
              </ListRow>
            ))}
          </List>
          <p className="text-muted-foreground px-1 text-xs">
            Tasks assigned to you in shared projects always show.
            {google.last_synced_at && ` Last synced ${new Date(google.last_synced_at).toLocaleString("en-GB")}.`}
          </p>
          <Button
            variant="outline"
            size="lg"
            onClick={async () => {
              if (!(await confirm("Disconnect Google Calendar? Its calendar of tasks is deleted.", "Disconnect"))) return;
              const { error } = await api.DELETE("/api/v1/todos/google/");
              if (error) toast.error(errorMessage(error));
              revalidate();
            }}
          >
            Disconnect
          </Button>
        </>
      ) : (
        <>
          {google?.status === "disconnected" && (
            <p className="text-destructive text-sm">Disconnected: access was removed in your Google account.</p>
          )}
          <Button size="lg" onClick={connect}>
            Connect Google Calendar
          </Button>
        </>
      )}
    </Sheet>
  );
}
