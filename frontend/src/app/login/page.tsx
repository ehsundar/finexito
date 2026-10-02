import { redirect } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { currentUser } from "@/lib/auth/current-user";
import { safeNext } from "@/lib/auth/session";
import { getSite } from "@/lib/site";

const ERRORS: Record<string, string> = {
  google: "Google sign-in did not complete. Please try again.",
  disabled: "This account has been disabled.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string; signed_out?: string }>;
}) {
  const { next, error, signed_out } = await searchParams;
  if (await currentUser()) redirect(safeNext(next));
  // Google is the only way in, so go straight there. The page still shows after
  // a failed attempt (or it would loop) and after signing out (or Google would
  // sign the visitor straight back in), and is here for when there are options.
  if (!error && signed_out === undefined) {
    redirect(`/auth/google?next=${encodeURIComponent(safeNext(next))}`);
  }
  const { name } = await getSite();

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Use your Google account to sign in to {name}, or to create your account.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{ERRORS[error] ?? ERRORS.google}</AlertDescription>
            </Alert>
          ) : (
            <p className="text-muted-foreground text-sm">You have signed out.</p>
          )}
          {/* A plain link: /auth/google is a route handler that redirects to Google. */}
          <a
            href={`/auth/google?next=${encodeURIComponent(safeNext(next))}`}
            className={buttonVariants({ size: "lg" })}
          >
            Continue with Google
          </a>
        </CardContent>
      </Card>
    </main>
  );
}
