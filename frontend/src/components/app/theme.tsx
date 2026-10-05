"use client";

import { useTheme } from "next-themes";
import { useEffect } from "react";
import { toast } from "sonner";

import { api, errorMessage, useQuery } from "@/lib/api/client";

export const THEMES = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
] as const;

export type Theme = (typeof THEMES)[number]["value"];

/**
 * The member's theme, kept in their profile (`extra.theme`) so every device
 * follows it; System until they pick one. Signed-in screens only: it reads
 * the profile. The profile is fetched again on focus, so a choice made on
 * another device shows up here.
 */
export function useProfileTheme() {
  const { setTheme } = useTheme();
  const { data: profile, mutate } = useQuery("/api/v1/profiles/me/");
  const saved = profile ? ((profile.extra?.theme as Theme | undefined) ?? "system") : null;

  // Only when the saved choice changes, so a pick here isn't undone mid-save.
  useEffect(() => {
    if (saved) setTheme(saved);
  }, [saved, setTheme]);

  async function choose(next: Theme) {
    if (!profile) return;
    const extra = { ...profile.extra, theme: next };
    await mutate({ ...profile, extra }, { revalidate: false });
    const { error } = await api.PATCH("/api/v1/profiles/me/", { body: { extra } });
    if (error) toast.error(errorMessage(error));
    await mutate();
  }

  return { theme: saved ?? "system", choose };
}
