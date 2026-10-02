import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { api } from "@/lib/api/client";
import { GOOGLE_COOKIE, safeNext, setSession } from "@/lib/auth/session";

/** Where Google sends the visitor back: the redirect URI registered with Google. */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const jar = await cookies();
  const pending = jar.get(GOOGLE_COOKIE)?.value;
  jar.delete(GOOGLE_COOKIE);

  const { state, verifier, next } = pending ? JSON.parse(pending) : {};
  const code = params.get("code");

  // A state that does not match the cookie means this browser never started the
  // sign-in: someone else's code, replayed here.
  if (!code || !state || params.get("state") !== state) {
    return redirectTo(request, "/login?error=google");
  }

  const { data, error } = await api.POST("/api/v1/auth/google/", {
    body: { code, code_verifier: verifier },
  });

  if (error || !data) {
    const reason = error?.error?.code === "account_disabled" ? "disabled" : "google";
    return redirectTo(request, `/login?error=${reason}`);
  }

  await setSession(data);
  return redirectTo(request, safeNext(next));
}

function redirectTo(request: NextRequest, path: string) {
  return NextResponse.redirect(new URL(path, request.nextUrl.origin));
}
