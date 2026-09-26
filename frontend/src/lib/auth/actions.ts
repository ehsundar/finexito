"use server";

import { redirect } from "next/navigation";

import { api, authedApi, errorMessage, fieldErrors, type ApiError } from "@/lib/api/client";
import { clearSession, getAccessToken, getRefreshToken, setSession } from "@/lib/auth/session";

export type FormState = {
  message?: string;
  /** A success notice, shown instead of an error. */
  notice?: string;
  fields?: Record<string, string>;
};

export async function login(_prev: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const { data, error } = await api.POST("/api/v1/auth/login/", {
    body: { email, password },
  });

  if ((error as ApiError | undefined)?.error?.code === "email_not_verified") {
    redirect(`/verify-email?email=${encodeURIComponent(email)}`);
  }

  if (error || !data) {
    return {
      message: errorMessage(error, "Those credentials were not accepted."),
      fields: fieldErrors(error),
    };
  }

  await setSession(data);
  redirect("/dashboard");
}

export async function register(_prev: FormState, formData: FormData): Promise<FormState> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const displayName = String(formData.get("display_name") ?? "");

  const { data, error } = await api.POST("/api/v1/auth/register/", {
    body: { email, password, display_name: displayName || undefined },
  });

  if (error || !data) {
    return {
      message: errorMessage(error, "We could not create that account."),
      fields: fieldErrors(error),
    };
  }

  // The account stays inactive until the emailed link is followed.
  redirect(`/verify-email?email=${encodeURIComponent(email)}`);
}

export async function verifyEmail(_prev: FormState, formData: FormData): Promise<FormState> {
  const uid = String(formData.get("uid") ?? "");
  const token = String(formData.get("token") ?? "");

  const { data, error } = await api.POST("/api/v1/auth/verify-email/", {
    body: { uid, token },
  });

  if (error || !data) {
    return { message: errorMessage(error, "This link is invalid or has already been used.") };
  }

  await setSession(data);
  redirect("/dashboard");
}

export async function resendVerification(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const email = String(formData.get("email") ?? "");

  const { data, error } = await api.POST("/api/v1/auth/verify-email/resend/", {
    body: { email },
  });

  if (error || !data) {
    return {
      message: errorMessage(error, "We could not send a new link."),
      fields: fieldErrors(error),
    };
  }

  return { notice: data.detail };
}

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
