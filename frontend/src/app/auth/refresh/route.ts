import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { api } from "@/lib/api/client";
import { clearSession, getRefreshToken, safeNext, setSession } from "@/lib/auth/session";

/**
 * Rotates an expired access token, then returns the visitor to where they were.
 *
 * `proxy.ts` sends requests here when the access cookie has expired but the
 * refresh cookie is still alive. The work happens in a route handler rather than
 * in the proxy itself, which only decides where a request goes.
 *
 * Redirects are relative (`redirect()`): behind Caddy this server only knows its
 * own bind address, so an absolute URL built from the request would point there.
 */
export async function GET(request: NextRequest) {
  const next = safeNext(request.nextUrl.searchParams.get("next"));
  const refresh = await getRefreshToken();

  if (!refresh) {
    redirect(loginUrl(next));
  }

  const { data, error } = await api.POST("/api/v1/auth/refresh/", { body: { refresh } });

  if (error || !data?.access) {
    await clearSession();
    redirect(loginUrl(next));
  }

  // ROTATE_REFRESH_TOKENS is on, so the old refresh token is blacklisted and a
  // new one comes back. Storing both keeps the session alive past this rotation.
  await setSession(data);
  redirect(next);
}

function loginUrl(next: string) {
  return `/login?next=${encodeURIComponent(next)}`;
}

