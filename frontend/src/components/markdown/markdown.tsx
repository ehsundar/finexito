"use client";

import { MarkdownHooks } from "react-markdown";
import remarkGfm from "remark-gfm";

import { markdownComponents } from "@/components/markdown/elements";
import { safeUrl } from "@/components/markdown/inline";
import { rehypeHighlight } from "@/components/markdown/highlight";
import { cn } from "@/lib/utils";

/**
 * Renders untrusted Markdown safely.
 *
 * - Raw HTML never reaches the DOM: `htmlAsText` turns it into plain text, which
 *   React escapes, so `<script>` shows up literally instead of running.
 * - `safeUrl` keeps only http(s), mailto and same-site URLs on links and images;
 *   `javascript:`, `data:` and the rest become empty.
 * - Nothing uses `dangerouslySetInnerHTML`.
 *
 * Fenced code blocks are highlighted in the browser (see highlight.ts); until
 * that is ready, the reader sees the source as plain text.
 */
export function Markdown({ source, className }: { source: string; className?: string }) {
  return (
    <div className={cn("text-base break-words", className)}>
      <MarkdownHooks
        components={markdownComponents}
        remarkPlugins={[remarkGfm, htmlAsText]}
        rehypePlugins={[rehypeHighlight]}
        urlTransform={safeUrl}
        fallback={<RawText source={source} />}
      >
        {source}
      </MarkdownHooks>
    </div>
  );
}

function RawText({ source }: { source: string }) {
  return (
    <pre className="font-sans text-base leading-7 whitespace-pre-wrap break-words">
      {source}
    </pre>
  );
}

type MdastNode = { type: string; value?: string; children?: MdastNode[] };

/** A remark plugin: raw HTML in the source is shown as the text it is. */
function htmlAsText() {
  return (tree: MdastNode) => {
    const walk = (node: MdastNode) => {
      if (node.type === "html") node.type = "text";
      node.children?.forEach(walk);
    };
    walk(tree);
  };
}
