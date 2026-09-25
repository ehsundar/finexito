"use client";

import { useActionState, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { FormState } from "@/lib/auth/actions";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

export function AuthForm({
  action,
  submitLabel,
  withDisplayName = false,
}: {
  action: Action;
  submitLabel: string;
  withDisplayName?: boolean;
}) {
  const [state, formAction, pending] = useActionState(action, {});
  const fields = state.fields ?? {};

  // React resets the form once a Server Action settles, which would wipe these
  // on a rejected submission. Controlled inputs keep what was typed; the
  // password is deliberately left uncontrolled so it clears itself.
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");

  return (
    <form action={formAction} className="flex flex-col gap-4">
      {state.message ? (
        <Alert variant="destructive">
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      ) : null}

      <Field
        name="email"
        label="Email"
        type="email"
        error={fields.email}
        value={email}
        onValueChange={setEmail}
        autoComplete="email"
      />

      {withDisplayName ? (
        <Field
          name="display_name"
          label="Display name"
          error={fields.display_name}
          value={displayName}
          onValueChange={setDisplayName}
          required={false}
        />
      ) : null}

      <Field
        name="password"
        label="Password"
        type="password"
        error={fields.password}
        autoComplete={withDisplayName ? "new-password" : "current-password"}
      />

      <Button type="submit" disabled={pending} className="mt-2">
        {pending ? "Working…" : submitLabel}
      </Button>
    </form>
  );
}

function Field({
  name,
  label,
  error,
  type = "text",
  value,
  onValueChange,
  required = true,
  autoComplete,
}: {
  name: string;
  label: string;
  error?: string;
  type?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  required?: boolean;
  autoComplete?: string;
}) {
  const controlled = onValueChange
    ? { value: value ?? "", onChange: (e: React.ChangeEvent<HTMLInputElement>) => onValueChange(e.target.value) }
    : {};

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={name}>{label}</Label>
      <Input
        id={name}
        name={name}
        type={type}
        autoComplete={autoComplete}
        required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : undefined}
        {...controlled}
      />
      {error ? (
        <p id={`${name}-error`} className="text-destructive text-sm">
          {error}
        </p>
      ) : null}
    </div>
  );
}
