"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AppBar, Screen } from "@/components/app/frame";
import { api, errorMessage } from "@/lib/api/client";

/** Where Google sends the browser back after consent; finishes connecting. */
export default function GoogleCallbackPage() {
  const params = useSearchParams();
  const router = useRouter();
  const code = params.get("code");
  const [error, setError] = useState(code ? "" : "Google didn't connect the calendar.");
  // Once, even when React runs the effect twice: the code works only once.
  const started = useRef(false);

  useEffect(() => {
    if (started.current || !code) return;
    started.current = true;
    const state = params.get("state") ?? "";
    api.GET("/api/v1/todos/google/callback/", { params: { query: { code, state } } }).then(({ error }) => {
      if (error) setError(errorMessage(error));
      else router.replace("/todos/browse");
    });
  }, [code, params, router]);

  return (
    <>
      <AppBar back="/todos/browse" title="Google Calendar" />
      <Screen>{error || "Connecting…"}</Screen>
    </>
  );
}
