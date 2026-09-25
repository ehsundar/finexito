import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth/auth-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { register } from "@/lib/auth/actions";
import { currentUser } from "@/lib/auth/current-user";

export default async function RegisterPage() {
  if (await currentUser()) redirect("/dashboard");

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create an account</CardTitle>
          <CardDescription>
            You are enrolled into the current program automatically where it allows it.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <AuthForm action={register} submitLabel="Create account" withDisplayName />
          <p className="text-muted-foreground text-sm">
            Already registered?{" "}
            <Link href="/login" className="text-foreground underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
