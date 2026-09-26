import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableRow } from "@/components/ui/table";
import { logout } from "@/lib/auth/actions";
import { requireUser, sessionApi } from "@/lib/auth/current-user";

export default async function DashboardPage() {
  const user = await requireUser();
  const api = await sessionApi();

  const { data: profile, error } = await api.GET("/api/v1/profiles/me/");

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Signed in as <span className="font-mono">{user.email}</span>
          </p>
        </div>
        <form action={logout}>
          <Button type="submit" variant="outline" size="sm">
            Sign out
          </Button>
        </form>
      </header>

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Read straight from the Django service.</CardDescription>
        </CardHeader>
        <CardContent>
          {error || !profile ? (
            <p className="text-destructive text-sm">Could not reach the API.</p>
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
