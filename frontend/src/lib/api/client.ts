import "server-only";

import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/lib/api/schema";

/**
 * Where the Django service lives.
 *
 * On Vercel this is injected by the `backend` service binding declared in
 * vercel.json, so it always points at the Django build from *this* deployment --
 * previews included. Locally `vercel dev` injects the same variable; plain
 * `next dev` falls back to the runserver default.
 */
export const backendOrigin =
  process.env.BACKEND_INTERNAL_URL ?? process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

/**
 * Re-issues the call as `fetch(url, init)` instead of `fetch(request)`.
 *
 * openapi-fetch always builds a `Request` object and hands that to fetch. Next's
 * instrumented fetch drops the body of a `Request` constructed that way, so every
 * POST and PATCH would reach Django with an empty body and fail validation --
 * silently, because the request itself is perfectly well formed. Unwrapping the
 * Request back into a URL and an init object keeps the body intact.
 *
 * Verified against Next 16.3.4. Worth retesting on a Next upgrade: if the bug is
 * gone, this whole indirection can go with it.
 */
const unwrappingFetch: typeof fetch = async (input, init) => {
  if (!(input instanceof Request)) {
    return globalThis.fetch(input, init);
  }

  const hasBody = input.method !== "GET" && input.method !== "HEAD";
  return globalThis.fetch(input.url, {
    method: input.method,
    headers: input.headers,
    body: hasBody ? await input.arrayBuffer() : undefined,
    redirect: input.redirect,
    signal: input.signal,
  });
};

/**
 * Django mounts everything under /api, and service bindings preserve the
 * original path, so the client's base URL carries no prefix of its own.
 */
function baseClient() {
  return createClient<paths>({ baseUrl: backendOrigin, fetch: unwrappingFetch });
}

/** Unauthenticated client, for login and registration. */
export const api = baseClient();

/**
 * Client that presents `token` as a bearer credential.
 *
 * Built per request rather than shared, because the token belongs to one
 * caller: a module-level authenticated client would leak it across requests.
 */
export function authedApi(token: string) {
  const client = baseClient();
  const auth: Middleware = {
    onRequest({ request }) {
      request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
  client.use(auth);
  return client;
}

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
