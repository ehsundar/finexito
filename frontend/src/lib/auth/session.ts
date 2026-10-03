/**
 * The signed-in session: the JWT pair Django hands out, kept in localStorage.
 * The browser calls Django itself, so it holds the tokens and sends the bearer
 * header (see lib/api/client.ts).
 */
type Tokens = { access: string; refresh: string };

const KEY = "session";

/** Holds the state and PKCE verifier (sessionStorage) while the visitor is away at Google. */
export const GOOGLE_KEY = "google_oauth";

/**
 * The admin's login page (backend/apps/accounts/admin.py) signs in whoever holds
 * this cookie, so the access token is mirrored here for /api/admin only.
 */
const ADMIN_COOKIE = "access_token";

export function getSession(): Tokens | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null");
  } catch {
    return null;
  }
}

export function setSession(tokens: Tokens) {
  localStorage.setItem(KEY, JSON.stringify({ access: tokens.access, refresh: tokens.refresh }));
  // Kept in step with ACCOUNTS_JWT_ACCESS_MINUTES on the backend.
  adminCookie(tokens.access, 30 * 60);
}

export function clearSession() {
  localStorage.removeItem(KEY);
  adminCookie("", 0);
}

function adminCookie(value: string, maxAge: number) {
  const secure = location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${ADMIN_COOKIE}=${value}; path=/api/admin; max-age=${maxAge}; samesite=lax${secure}`;
}

/**
 * Only ever go to a path on this origin. A protocol-relative value such as
 * `//evil.example` would otherwise send the visitor off-site.
 */
export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/dashboard";
  }
  return value;
}
