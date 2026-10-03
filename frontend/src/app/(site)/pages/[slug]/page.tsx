import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { cache } from "react";

import { Markdown } from "@/components/markdown/markdown";
import { Badge } from "@/components/ui/badge";
import { api, authedApi } from "@/lib/api/client";
import { getAccessToken, getRefreshToken } from "@/lib/auth/session";

/**
 * Pages are readable without a session, so this route sits outside the proxy's
 * guard and sends the session along only when there is one.
 */
const getPage = cache(async (slug: string) => {
  const token = await getAccessToken();
  const client = token ? authedApi(token) : api;
  const { data, error, response } = await client.GET("/api/v1/pages/{slug}/", {
    params: { path: { slug } },
  });

  if (data) return data;
  if (response.status === 404) notFound();
  if (response.status === 401) {
    // A private page, or an expired session: rotate if we can, else sign in.
    const next = encodeURIComponent(`/pages/${slug}`);
    redirect((await getRefreshToken()) ? `/auth/refresh?next=${next}` : `/login?next=${next}`);
  }
  throw new Error(`Could not load page "${slug}": ${response.status}`, { cause: error });
});

export async function generateMetadata({ params }: PageProps<"/pages/[slug]">): Promise<Metadata> {
  const page = await getPage((await params).slug);
  return { title: page.title, description: page.summary || undefined };
}

export default async function ContentPage({ params }: PageProps<"/pages/[slug]">) {
  const page = await getPage((await params).slug);
  const published = page.published_at ? new Date(page.published_at) : null;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
      <article>
        <header className="mb-8 flex flex-col gap-3 border-b pb-6">
          <h1 className="text-3xl font-semibold tracking-tight break-words sm:text-4xl">
            {page.title}
          </h1>
          {page.summary && <p className="text-muted-foreground text-lg">{page.summary}</p>}
          <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-sm">
            {published && (
              <time dateTime={published.toISOString()}>
                {published.toLocaleDateString("en-GB", { dateStyle: "long" })}
              </time>
            )}
            {page.visibility === "private" && <Badge variant="secondary">Members only</Badge>}
          </div>
        </header>
        <Markdown source={page.body} />
      </article>
    </main>
  );
}
