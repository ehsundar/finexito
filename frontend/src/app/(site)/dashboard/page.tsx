"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableRow } from "@/components/ui/table";
import { api, useQuery } from "@/lib/api/client";
import { clearSession, getSession } from "@/lib/auth/session";

export default function DashboardPage() {
  const router = useRouter();
  const { data: user } = useQuery("/api/v1/auth/me/");
  const { data: profile, error } = useQuery("/api/v1/profiles/me/");

  async function logout() {
    // Blacklist the refresh token so it cannot be rotated after we drop it. A
    // failure is not worth blocking sign-out over: forgetting the tokens is what
    // ends the session in this browser.
    const refresh = getSession()?.refresh;
    if (refresh) await api.POST("/api/v1/auth/logout/", { body: { refresh } }).catch(() => undefined);
    clearSession();
    // Apps' offline copies (the todos client's) go with the session.
    for (const { name } of (await indexedDB.databases?.()) ?? []) if (name) indexedDB.deleteDatabase(name);
    router.replace("/");
  }

  if (!user) return null;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Signed in as <span className="font-mono">{user.email}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/todos" />}>
            Todos
          </Button>
          <Button variant="outline" size="sm" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Read straight from the Django service.</CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-destructive text-sm">Could not reach the API.</p>
          ) : profile && (
            <Table>
              <TableBody>
                <TableRow>
                  <TableHead>Display name</TableHead>
                  <TableCell className="font-medium">{profile.display_name}</TableCell>
                </TableRow>
                <TableRow>
                  <TableHead>Role</TableHead>
                  <TableCell>
                    <Badge variant="secondary">{profile.role}</Badge>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableHead>Locale</TableHead>
                  <TableCell className="font-mono text-muted-foreground">
                    {profile.locale}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
