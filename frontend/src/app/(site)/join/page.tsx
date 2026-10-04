"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { joinProject } from "@/app/todos/actions";
import { Avatar } from "@/app/todos/people";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuery } from "@/lib/api/client";
import { getSession } from "@/lib/auth/session";

/**
 * `?token=`: a project's invite link. Anyone holding it sees what they're
 * invited to; signing in (or up) brings them back here to join.
 */
export default function JoinPage() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const { data: invite, error } = useQuery("/api/v1/todos/join/{token}/", { params: { path: { token } } });
  const [busy, setBusy] = useState(false);
  const signedIn = typeof window !== "undefined" && !!getSession();
  const open = (project: string) => router.push(`/todos/project?id=${project}`);

  if (error)
    return (
      <main className="flex flex-1 items-center justify-center p-6">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>This invite link doesn&apos;t work any more</CardTitle>
            <CardDescription>Ask whoever sent it for a new one.</CardDescription>
          </CardHeader>
        </Card>
      </main>
    );
  if (!invite) return null;

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Join “{invite.name}”</CardTitle>
          <CardDescription className="flex items-center gap-2">
            <Avatar person={invite.invited_by} />
            {invite.invited_by.name} invited you to work on this project together.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {invite.is_member ? (
            <Button size="lg" onClick={() => open(invite.project)}>
              Open project
            </Button>
          ) : invite.is_full ? (
            <p className="text-muted-foreground text-sm">This project is full.</p>
          ) : signedIn ? (
            <Button
              size="lg"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                const { error } = await joinProject(token);
                setBusy(false);
                if (error) return toast.error(error);
                open(invite.project);
              }}
            >
              Join project
            </Button>
          ) : (
            <Button
              size="lg"
              onClick={() => router.push(`/login?next=${encodeURIComponent(`/join?token=${token}`)}`)}
            >
              Sign in with Google to join
            </Button>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
