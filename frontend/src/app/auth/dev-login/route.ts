import { notFound } from "next/navigation";
import { NextResponse, type NextRequest } from "next/server";

import { setSession } from "@/lib/auth/session";

/**
 * Development only: signs in with the tokens `manage.py login_as <email>` prints,
 * so you can be anyone locally without going through Google.
 */
export async function GET(request: NextRequest) {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  const access = request.nextUrl.searchParams.get("access");
  const refresh = request.nextUrl.searchParams.get("refresh");
  if (!access || !refresh) {
    notFound();
  }

  await setSession({ access, refresh });
  return NextResponse.redirect(new URL("/dashboard", request.nextUrl.origin));
}
