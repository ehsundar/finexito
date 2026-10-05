"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Pending } from "@/components/app/pending";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableRow } from "@/components/ui/table";
import { signOut, useQuery } from "@/lib/api/client";

export default function DashboardPage() {
  const router = useRouter();
  const { data: user, error: userError } = useQuery("/api/v1/auth/me/");
  const { data: profile, error } = useQuery("/api/v1/profiles/me/");

  async function logout() {
    await signOut();
    router.replace("/");
  }

  if (!user) return <Pending error={userError} />;

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
          {!profile ? (
            <Pending error={error} />
          ) : (
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
