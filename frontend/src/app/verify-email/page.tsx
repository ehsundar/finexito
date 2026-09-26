import Link from "next/link";

import { ConfirmEmailForm, ResendVerificationForm } from "@/components/auth/verify-email-forms";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ uid?: string; token?: string; email?: string }>;
}) {
  const { uid, token, email } = await searchParams;
  const fromLink = Boolean(uid && token);

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{fromLink ? "Activate your account" : "Check your email"}</CardTitle>
          <CardDescription>
            {fromLink
              ? "Confirm your email address to finish setting up your account."
              : "We sent you a link to activate your account. It is valid for a limited time."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {fromLink ? <ConfirmEmailForm uid={uid!} token={token!} /> : null}
          <ResendVerificationForm initialEmail={email} />
          <p className="text-muted-foreground text-sm">
            Already verified?{" "}
            <Link href="/login" className="text-foreground underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
