"use client";

import { useActionState, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { resendVerification, verifyEmail } from "@/lib/auth/actions";

/**
 * Activation takes a click rather than happening on page load, because mail
 * scanners fetch links ahead of the recipient and would spend the one-time token.
 */
export function ConfirmEmailForm({ uid, token }: { uid: string; token: string }) {
  const [state, formAction, pending] = useActionState(verifyEmail, {});

  return (
    <form action={formAction} className="flex flex-col gap-4">
      {state.message ? (
        <Alert variant="destructive">
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      ) : null}
      <input type="hidden" name="uid" value={uid} />
      <input type="hidden" name="token" value={token} />
      <Button type="submit" disabled={pending}>
        {pending ? "Working…" : "Activate account"}
      </Button>
    </form>
  );
}

export function ResendVerificationForm({ initialEmail = "" }: { initialEmail?: string }) {
  const [state, formAction, pending] = useActionState(resendVerification, {});
  const [email, setEmail] = useState(initialEmail);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      {state.message ? (
        <Alert variant="destructive">
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      ) : null}
      {state.notice ? (
        <Alert>
          <AlertDescription>{state.notice}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={Boolean(state.fields?.email)}
        />
        {state.fields?.email ? (
          <p className="text-destructive text-sm">{state.fields.email}</p>
        ) : null}
      </div>
      <Button type="submit" variant="outline" disabled={pending}>
        {pending ? "Sending…" : "Send a new link"}
      </Button>
    </form>
  );
}
