import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { api } from "@/lib/api/client";
import { GOOGLE_COOKIE, safeNext, sharedCookie } from "@/lib/auth/session";

/**
 * Starts Google sign-in. Django builds the authorisation URL; the state and PKCE
 * verifier wait in a short-lived cookie until Google sends the visitor back to
 * /auth/google/callback.
 */
export async function GET(request: NextRequest) {
  const next = safeNext(request.nextUrl.searchParams.get("next"));
  const { data } = await api.POST("/api/v1/auth/google/start/");

  if (!data) {
    redirect("/login?error=google");
  }

  (await cookies()).set(
    GOOGLE_COOKIE,
    JSON.stringify({ state: data.state, verifier: data.code_verifier, next }),
    { ...sharedCookie, maxAge: 10 * 60 },
  );
  redirect(data.url);
}
