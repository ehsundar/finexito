import useSWR from "swr";

const manifest = `${process.env.NEXT_PUBLIC_API_ORIGIN ?? ""}/api/v1/manifest.webmanifest`;

/**
 * What this deployment is called. Django's SITE_NAME is the only source, read
 * from the web app manifest: the frontend is shared by every white-labelled
 * deployment and names none of them.
 */
export function useSiteName() {
  const { data } = useSWR<{ name: string }>(manifest, (url: string) =>
    fetch(url).then((response) => response.json()),
  );
  return data?.name ?? "";
}
