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
const configured = process.env.NEXT_PUBLIC_API_ORIGIN ?? "";
const loopback = /^(127\.0\.0\.1|localhost)$/;
// `next dev` opened from a phone by this machine's address: runserver is on
// this machine too, not on the phone's own loopback.
const baseUrl =
  typeof location !== "undefined" && !loopback.test(location.hostname)
    ? configured.replace(/\/\/(127\.0\.0\.1|localhost)(?=[:/]|$)/, `//${location.hostname}`)
    : configured;

/** A path Django hands out (a signed file link), as the browser can open it. */
export const apiUrl = (path: string) => baseUrl + path;

/** No credentials and no retries: only for rotating the tokens. */
const bare = createClient<paths>({ baseUrl });

let refreshing: Promise<boolean> | null = null;

/**
 * Swaps the refresh token for a new pair (ROTATE_REFRESH_TOKENS is on). Calls
 * that hit a 401 together share one rotation, since each token works only once.
 *
 * The session ends only when Django rejects the token, so signing in with Google
 * again is needed once in ACCOUNTS_JWT_REFRESH_DAYS, not whenever a cookie or
 * access token expires. Another tab rotating first (the old token is then
 * blacklisted) or a server error leave it alone.
 */
export function refresh() {
  refreshing ??= (async () => {
    const token = getSession()?.refresh;
    if (!token) return false;
    const { data, response } = await bare.POST("/api/v1/auth/refresh/", { body: { refresh: token } });
    if (data) {
      setSession(data);
      syncTimezone();
      return true;
    }
    if (getSession()?.refresh !== token) return true;
    if (response.status === 401) clearSession();
    return false;
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
  // Still a session: the server failed, not the sign-in. Let the caller show it.
  if (getSession()) return response;
  if (!location.pathname.startsWith("/login")) {
    location.replace(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
  }
  return response;
}

type Offline = (request: Request, network: (request: Request) => Promise<Response>) => Promise<Response>;
let offline: Offline | null = null;

/** Lets an app answer its calls when the server can't be reached (the todos client's offline.ts). */
export function handleOffline(handler: Offline | null) {
  offline = handler;
}

export const api = createClient<paths>({
  baseUrl,
  fetch: (request) => (offline ? offline(request, authedFetch) : authedFetch(request)),
});

/**
 * Starts a session from fresh tokens, noting whether it belongs to staff (see
 * session.ts), and says whether it does.
 */
export async function signIn(tokens: { access: string; refresh: string }) {
  setSession({ ...tokens, staff: false });
  const { data: me } = await api.GET("/api/v1/auth/me/");
  const staff = !!me?.is_staff;
  // The call above may have rotated the tokens; keep the newest.
  const current = getSession();
  if (current) setSession({ ...current, staff });
  syncTimezone();
  return staff;
}

/**
 * Ends the session in this browser. The refresh token is blacklisted first so it
 * can't be rotated after we drop it; a failure there isn't worth blocking
 * sign-out over, since forgetting the tokens is what ends it here. Apps' offline
 * copies (the todos client's) go with it.
 */
export async function signOut() {
  const refresh = getSession()?.refresh;
  if (refresh) await api.POST("/api/v1/auth/logout/", { body: { refresh } }).catch(() => undefined);
  clearSession();
  for (const { name } of (await indexedDB.databases?.()) ?? []) if (name) indexedDB.deleteDatabase(name);
}

/**
 * Dates are the member's, in the zone of the device they're using now, so the
 * profile takes it whenever tokens are issued: at sign-in and on each refresh.
 */
function syncTimezone() {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  if (timezone) void api.PATCH("/api/v1/profiles/me/", { body: { timezone } });
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
