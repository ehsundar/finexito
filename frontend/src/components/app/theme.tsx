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

/** The palettes in colours.css; "default" is the brand's own. */
export const PALETTES = [
  { value: "default", label: "Default" },
  { value: "vinyl", label: "Vinyl" },
  { value: "cherry", label: "Cherry" },
  { value: "robins-egg", label: "Robin's egg" },
  { value: "papaya", label: "Papaya" },
  { value: "plum", label: "Plum" },
  { value: "bubblegum", label: "Bubblegum" },
  { value: "evergreen", label: "Evergreen" },
  { value: "midsummer", label: "Midsummer" },
  { value: "espresso", label: "Espresso" },
  { value: "periwinkle", label: "Periwinkle" },
  { value: "noir", label: "Noir" },
] as const;

export type Palette = (typeof PALETTES)[number]["value"];

// Set before React loads (app/layout.tsx), so a page opens in its palette.
export const PALETTE_SCRIPT = `document.documentElement.dataset.palette = localStorage.getItem("palette") || "default"`;

/**
 * The member's theme and palette, kept in their profile (`extra.theme`,
 * `extra.palette`) so every device
 * follows it; System until they pick one. Signed-in screens only: it reads
 * the profile. The profile is fetched again on focus, so a choice made on
 * another device shows up here.
 */
export function useProfileTheme() {
  const { setTheme } = useTheme();
  const { data: profile, mutate } = useQuery("/api/v1/profiles/me/");
  const saved = profile ? ((profile.extra?.theme as Theme | undefined) ?? "system") : null;
  const palette = profile ? ((profile.extra?.palette as Palette | undefined) ?? "default") : null;

  // Only when the saved choice changes, so a pick here isn't undone mid-save.
  useEffect(() => {
    if (saved) setTheme(saved);
  }, [saved, setTheme]);

  useEffect(() => {
    if (!palette) return;
    document.documentElement.dataset.palette = palette;
    localStorage.setItem("palette", palette);
  }, [palette]);

  async function choose(next: { theme?: Theme; palette?: Palette }) {
    if (!profile) return;
    const extra = { ...profile.extra, ...next };
    await mutate({ ...profile, extra }, { revalidate: false });
    const { error } = await api.PATCH("/api/v1/profiles/me/", { body: { extra } });
    if (error) toast.error(errorMessage(error));
    await mutate();
  }

  return { theme: saved ?? "system", palette: palette ?? "default", choose };
}
