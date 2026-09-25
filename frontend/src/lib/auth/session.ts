import "server-only";

import { cookies } from "next/headers";

import type { components } from "@/lib/api/schema";

export type User = components["schemas"]["User"];

export const ACCESS_COOKIE = "access_token";
export const REFRESH_COOKIE = "refresh_token";

/**
 * Tokens live in httpOnly cookies, never in localStorage, so a script injected
 * into the page cannot read them. The browser therefore never holds a usable
 * credential: every authenticated call goes through the server, which attaches
 * the bearer header itself.
 */
const shared = {
  httpOnly: true,
  sameSite: "lax",
  // SECURE_COOKIES=false only while the site is served over plain HTTP (a bare
  // IP, no domain yet): browsers drop Secure cookies on http://, so nobody could
  // stay signed in.
  secure: process.env.NODE_ENV === "production" && process.env.SECURE_COOKIES !== "false",
  path: "/",
} as const;

/** Kept in step with JWT_ACCESS_MINUTES / JWT_REFRESH_DAYS on the backend. */
const ACCESS_MAX_AGE = 30 * 60;
const REFRESH_MAX_AGE = 14 * 24 * 60 * 60;

export async function setSession(tokens: { access: string; refresh: string }) {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, tokens.access, { ...shared, maxAge: ACCESS_MAX_AGE });
  jar.set(REFRESH_COOKIE, tokens.refresh, { ...shared, maxAge: REFRESH_MAX_AGE });
}

export async function setAccessToken(access: string) {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, access, { ...shared, maxAge: ACCESS_MAX_AGE });
}

export async function clearSession() {
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
}

export async function getAccessToken() {
  return (await cookies()).get(ACCESS_COOKIE)?.value;
}

export async function getRefreshToken() {
  return (await cookies()).get(REFRESH_COOKIE)?.value;
}
