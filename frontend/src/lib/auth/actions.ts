"use server";

import { redirect } from "next/navigation";

import { authedApi } from "@/lib/api/client";
import { clearSession, getAccessToken, getRefreshToken } from "@/lib/auth/session";

export async function logout() {
  const access = await getAccessToken();
  const refresh = await getRefreshToken();

  // Blacklist the refresh token so it cannot be rotated after we drop the
  // cookies. A failure here is not worth blocking sign-out over: clearing the
  // cookies is what actually ends the session in this browser.
  if (access && refresh) {
    await authedApi(access)
      .POST("/api/v1/auth/logout/", { body: { refresh } })
      .catch(() => undefined);
  }

  await clearSession();
  redirect("/login");
}
