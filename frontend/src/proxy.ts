import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth/session";

/**
 * An optimistic guard, not an authorisation check.
 *
 * It only looks at whether session cookies are present, which is cheap enough to
 * run on every navigation. The tokens are still verified by Django on each call,
 * so a forged cookie buys a visitor nothing but a rendered shell.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasAccess = request.cookies.has(ACCESS_COOKIE);
  const hasRefresh = request.cookies.has(REFRESH_COOKIE);

  if (hasAccess) {
    return NextResponse.next();
  }

  // The access cookie's lifetime matches the token's, so its absence alongside a
  // live refresh cookie means exactly one thing: time to rotate.
  if (hasRefresh) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/refresh";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }

  const login = request.nextUrl.clone();
  login.pathname = "/login";
  login.search = `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(login);
}

export const config = {
  /**
   * Guard the signed-in area only. Everything else -- the login page, the
   * refresh handler, static assets -- must stay reachable without a session.
   */
  matcher: ["/dashboard/:path*", "/account/:path*"],
};
