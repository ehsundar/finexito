import createClient from "openapi-fetch";
import { mutate } from "swr";
import { createQueryHook } from "swr-openapi";

import type { paths } from "@/lib/api/schema";
import { clearSession, getSession, setSession } from "@/lib/auth/session";

/**
 * The browser calls Django directly. In production Caddy serves both on one
 * domain, so paths stay relative; `next dev` points at runserver through
 * NEXT_PUBLIC_API_ORIGIN (DEBUG lets any origin through CORS).
 */
const baseUrl = process.env.NEXT_PUBLIC_API_ORIGIN ?? "";

/** No credentials and no retries: only for rotating the tokens. */
const bare = createClient<paths>({ baseUrl });

let refreshing: Promise<boolean> | null = null;

/**
 * Swaps the refresh token for a new pair (ROTATE_REFRESH_TOKENS is on). Calls
 * that hit a 401 together share one rotation, since each token works only once.
 */
export function refresh() {
  refreshing ??= (async () => {
    const token = getSession()?.refresh;
    const { data } = token
      ? await bare.POST("/api/v1/auth/refresh/", { body: { refresh: token } })
      : { data: undefined };
    if (data) setSession(data);
    else clearSession();
    return !!data;
  })().finally(() => (refreshing = null));
  return refreshing;
}

function signed(request: Request) {
  const access = getSession()?.access;
  if (access) request.headers.set("Authorization", `Bearer ${access}`);
  return request;
}

/**
 * Sends the bearer token. On a 401 it rotates the tokens and tries once more;
 * when that fails the session is over, so the visitor goes to sign in.
 */
async function authedFetch(request: Request) {
  const retry = request.clone();
  const response = await fetch(signed(request));
  if (response.status !== 401) return response;
  if (await refresh()) return fetch(signed(retry));
  if (!location.pathname.startsWith("/login")) {
    location.replace(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
  }
  return response;
}

export const api = createClient<paths>({ baseUrl, fetch: authedFetch });

/** Starts a session from a fresh sign-in, noting whether it belongs to staff. */
export async function signIn(tokens: { access: string; refresh: string }) {
  setSession({ ...tokens, staff: false });
  const { data: me } = await api.GET("/api/v1/auth/me/");
  setSession({ ...tokens, staff: !!me?.is_staff });
}

/** `useQuery(path, init)`: a GET through `api`, cached and revalidated by SWR. */
export const useQuery = createQueryHook(api, "api");

/** Fetches every query on screen again, after a write. */
export const revalidate = () => mutate(() => true);

/** The error envelope that `apps.common.exceptions` puts on every failure. */
export type ApiError = {
  error: { code: string; message: string; fields: Record<string, unknown> };
};

export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  const envelope = error as ApiError | undefined;
  return envelope?.error?.message ?? fallback;
}

/** Field-level validation messages, keyed by form field name. */
export function fieldErrors(error: unknown): Record<string, string> {
  const fields = (error as ApiError | undefined)?.error?.fields ?? {};
  return Object.fromEntries(
    Object.entries(fields).map(([key, value]) => [
      key,
      Array.isArray(value) ? String(value[0]) : String(value),
    ]),
  );
}
