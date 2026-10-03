"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, refresh, signIn } from "@/lib/api/client";
import { clearSession, getSession, GOOGLE_KEY, safeNext } from "@/lib/auth/session";
import { useSiteName } from "@/lib/site";

const ERRORS: Record<string, string> = {
  google: "Google sign-in did not complete. Please try again.",
  disabled: "This account has been disabled.",
  staff: "This account can't use the admin.",
  unreachable: "Couldn't reach the server. Please try again.",
};

/** Django builds Google's URL; the state and verifier wait here for the callback. */
async function startGoogle(next: string) {
  clearSession();
  const { data } = await api.POST("/api/v1/auth/google/start/");
  if (!data) return location.replace("/login?error=google");
  sessionStorage.setItem(
    GOOGLE_KEY,
    JSON.stringify({ state: data.state, verifier: data.code_verifier, next }),
  );
  location.assign(data.url);
}

export default function LoginPage() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const error = params.get("error");
  const signedOut = params.has("signed_out");
  const name = useSiteName();

  // Google is the only way in, so go straight there. The page still shows after
  // a failed attempt (or it would loop) and after signing out (or Google would
  // sign the visitor straight back in), and is here for when there are options.
  // A live session goes on, with fresh tokens: the admin sends visitors here for
  // its cookie. A full load, since `next` may be outside this app (/api/admin).
  useEffect(() => {
    if (error || signedOut) return;
    (async () => {
      const session = getSession();
      if (!session) return startGoogle(next);
      if (!(await refresh())) {
        // Google only when Django has ended the session; a server error keeps it.
        if (getSession()) return location.replace(`/login?error=unreachable&next=${encodeURIComponent(next)}`);
        return startGoogle(next);
      }
      // Ask again who is staff: it decides the admin's cookie, and a session
      // from before the flag existed doesn't know.
      const staff = await signIn(getSession() ?? session);
      if (next.startsWith("/api/admin") && !staff) location.replace("/login?error=staff");
      else location.replace(next);
    })();
  }, [error, signedOut, next]);

  if (!error && !signedOut) return null;
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
          <Button size="lg" onClick={() => startGoogle(next)}>
            Continue with Google
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
