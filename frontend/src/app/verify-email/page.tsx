import Link from "next/link";

import { ConfirmEmailForm, ResendVerificationForm } from "@/components/auth/verify-email-forms";
import { buttonVariants } from "@/components/ui/button";
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
              : "We sent you a link. Open it to activate your account, then sign in."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {fromLink ? (
            <ConfirmEmailForm uid={uid!} token={token!} />
          ) : (
            <Link href="/login" className={buttonVariants({ size: "lg" })}>
              Activated? Go to sign in
            </Link>
          )}
          <div className="flex flex-col gap-3 border-t pt-6">
            <p className="text-muted-foreground text-sm">No email? Send yourself a new link.</p>
            <ResendVerificationForm initialEmail={email} />
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
