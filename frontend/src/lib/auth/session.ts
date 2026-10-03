/**
 * The signed-in session: the JWT pair Django hands out, kept in localStorage.
 * The browser calls Django itself, so it holds the tokens and sends the bearer
 * header (see lib/api/client.ts).
 */
type Tokens = { access: string; refresh: string };
/** `staff` comes from /auth/me/ at sign-in (signIn in lib/api/client.ts). */
type Session = Tokens & { staff?: boolean };

const KEY = "session";

/** Holds the state and PKCE verifier (sessionStorage) while the visitor is away at Google. */
export const GOOGLE_KEY = "google_oauth";

/**
 * The admin's login page (backend/apps/accounts/admin.py) signs in whoever holds
 * this cookie, so a staff member's access token is mirrored here, for /api/admin
 * only. Nobody else gets it: the admin would refuse them anyway.
 */
const ADMIN_COOKIE = "access_token";

export function getSession(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null");
  } catch {
    return null;
  }
}

/** Stores the tokens. A refresh doesn't say who is staff, so the flag carries over. */
export function setSession({ access, refresh, staff = getSession()?.staff ?? false }: Session) {
  localStorage.setItem(KEY, JSON.stringify({ access, refresh, staff }));
  // Kept in step with ACCOUNTS_JWT_ACCESS_MINUTES on the backend.
  if (staff) adminCookie(access, 30 * 60);
  else adminCookie("", 0);
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
