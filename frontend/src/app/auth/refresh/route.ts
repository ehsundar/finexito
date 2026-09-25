import { NextResponse, type NextRequest } from "next/server";

import { api } from "@/lib/api/client";
import { clearSession, getRefreshToken, setSession } from "@/lib/auth/session";

/**
 * Rotates an expired access token, then returns the visitor to where they were.
 *
 * `proxy.ts` sends requests here when the access cookie has expired but the
 * refresh cookie is still alive. The work happens in a route handler rather than
 * in the proxy itself because service bindings -- how we reach Django on Vercel
 * -- are injected into functions, not into the proxy layer.
 */
export async function GET(request: NextRequest) {
  const next = safeNext(request.nextUrl.searchParams.get("next"));
  const refresh = await getRefreshToken();

  if (!refresh) {
    return redirectTo(request, loginUrl(next));
  }

  const { data, error } = await api.POST("/api/v1/auth/refresh/", { body: { refresh } });

  if (error || !data?.access) {
    await clearSession();
    return redirectTo(request, loginUrl(next));
  }

  // ROTATE_REFRESH_TOKENS is on, so the old refresh token is blacklisted and a
  // new one comes back. Storing both keeps the session alive past this rotation.
  await setSession(data);
  return redirectTo(request, next);
}

function loginUrl(next: string) {
  return `/login?next=${encodeURIComponent(next)}`;
}

function redirectTo(request: NextRequest, path: string) {
  return NextResponse.redirect(new URL(path, request.nextUrl.origin));
}

/**
 * Only ever redirect to a path on this origin. A protocol-relative value such
 * as `//evil.example` would otherwise send the visitor off-site.
 */
function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/dashboard";
  }
  return value;
}
