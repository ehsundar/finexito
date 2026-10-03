import { useQuery } from "@/lib/api/client";

/**
 * What this deployment is called. Django's SITE_NAME is the only source: the
 * frontend is shared by every white-labelled deployment and names none of them.
 */
export function useSiteName() {
  return useQuery("/api/v1/site/").data?.name ?? "";
}
