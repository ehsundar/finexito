import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth/auth-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { login } from "@/lib/auth/actions";
import { currentUser } from "@/lib/auth/current-user";
import { getSite } from "@/lib/site";

export default async function LoginPage() {
  if (await currentUser()) redirect("/dashboard");
  const { name } = await getSite();

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Use your {name} account.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <AuthForm action={login} submitLabel="Sign in" />
          <p className="text-muted-foreground text-sm">
            No account yet?{" "}
            <Link href="/register" className="text-foreground underline underline-offset-4">
              Create one
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
