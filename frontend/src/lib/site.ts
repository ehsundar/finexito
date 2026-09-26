import "server-only";

import { connection } from "next/server";
import { cache } from "react";

import { api } from "@/lib/api/client";

/**
 * What this deployment is called. Django's SITE_NAME is the only source: the
 * frontend is shared by every white-labelled deployment and names none of them.
 *
 * Read per request, never at build time: images are built once, without a
 * backend, and the name belongs to whichever deployment runs them.
 */
export const getSite = cache(async () => {
  await connection();
  try {
    const { data } = await api.GET("/api/v1/site/");
    return { name: data?.name ?? "" };
  } catch {
    return { name: "" };
  }
});
