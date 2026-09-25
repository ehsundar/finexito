import "server-only";

import { redirect } from "next/navigation";

import { authedApi } from "@/lib/api/client";
import { getAccessToken, type User } from "@/lib/auth/session";

/**
 * The signed-in account, or `null` when there is no usable session.
 *
 * Server Components cannot write cookies, so this does not attempt a refresh --
 * `proxy.ts` has already rotated the token by the time a guarded page renders.
 */
export async function currentUser(): Promise<User | null> {
  const token = await getAccessToken();
  if (!token) return null;

  const { data, error } = await authedApi(token).GET("/api/v1/auth/me/");
  return error || !data ? null : data;
}

/** As above, but sends visitors without a session to the login page. */
export async function requireUser(): Promise<User> {
  const user = await currentUser();
  if (!user) redirect("/login");
  return user;
}

/** An API client bound to the current session, for use inside guarded pages. */
export async function sessionApi() {
  const token = await getAccessToken();
  if (!token) redirect("/login");
  return authedApi(token);
}
