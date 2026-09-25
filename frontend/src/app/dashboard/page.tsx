import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { logout } from "@/lib/auth/actions";
import { requireUser, sessionApi } from "@/lib/auth/current-user";

export default async function DashboardPage() {
  const user = await requireUser();
  const api = await sessionApi();

  const { data, error } = await api.GET("/api/v1/programs/", {
    params: { query: { page_size: 20 } },
  });
  const programs = data?.results ?? [];

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Programs</h1>
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
          <CardTitle>Catalogue</CardTitle>
          <CardDescription>
            Every program this instance serves, read straight from the Django service.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-destructive text-sm">Could not reach the API.</p>
          ) : programs.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No programs yet. Create one with{" "}
              <code className="font-mono">manage.py createprogram</code>.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Enrolment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {programs.map((program) => (
                  <TableRow key={program.id}>
                    <TableCell className="font-medium">{program.name}</TableCell>
                    <TableCell className="font-mono text-muted-foreground">
                      {program.slug}
                    </TableCell>
                    <TableCell>
                      <Badge variant={program.allow_self_enrolment ? "default" : "secondary"}>
                        {program.allow_self_enrolment ? "Open" : "Invite only"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
