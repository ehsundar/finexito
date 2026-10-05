"use client";

import { useSearchParams } from "next/navigation";

import { Pending } from "@/components/app/pending";
import { Markdown } from "@/components/markdown/markdown";
import { Badge } from "@/components/ui/badge";
import { useQuery } from "@/lib/api/client";

/**
 * `?slug=`: the page. Readable without a session; a private one answers 401,
 * which signs the visitor in (lib/api/client.ts) and brings them back.
 */
export default function ContentPage() {
  const slug = useSearchParams().get("slug") ?? "";
  const { data: page, error } = useQuery("/api/v1/pages/{slug}/", { params: { path: { slug } } });
  if (!page) return <Pending error={error} missing="This page could not be found." />;
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
