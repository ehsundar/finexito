"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { api, signIn } from "@/lib/api/client";
import { GOOGLE_KEY, safeNext } from "@/lib/auth/session";

/** Where Google sends the visitor back: the redirect URI registered with Google. */
export default function GoogleCallbackPage() {
  const params = useSearchParams();
  // A code is good for one exchange, and the pending state is taken as it's
  // read, so finish once even when React runs the effect twice (development).
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const pending = sessionStorage.getItem(GOOGLE_KEY);
    sessionStorage.removeItem(GOOGLE_KEY);
    const { state, verifier, next } = pending ? JSON.parse(pending) : ({} as Record<string, string>);
    const code = params.get("code");

    (async () => {
      // A state that does not match means this browser never started the
      // sign-in: someone else's code, replayed here.
      if (!code || !state || params.get("state") !== state) {
        return location.replace("/login?error=google");
      }
      const { data, error } = await api.POST("/api/v1/auth/google/", {
        body: { code, code_verifier: verifier },
      });
      if (error || !data) {
        const reason = error?.error?.code === "account_disabled" ? "disabled" : "google";
        return location.replace(`/login?error=${reason}`);
      }
      await signIn(data);
      location.replace(safeNext(next));
    })();
  }, [params]);

  return null;
}
