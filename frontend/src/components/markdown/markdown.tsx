import { MarkdownAsync, type UrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { markdownComponents } from "@/components/markdown/elements";
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
 * Fenced code blocks are highlighted on the server (see highlight.ts).
 *
 * Rendering hardly ever fails, but if it does the reader gets the source
 * as plain text rather than an error page.
 */
export async function Markdown({ source, className }: { source: string; className?: string }) {
  let rendered: React.ReactElement;
  try {
    rendered = await MarkdownAsync({
      children: source,
      components: markdownComponents,
      remarkPlugins: [remarkGfm, htmlAsText],
      rehypePlugins: [await rehypeHighlight()],
      urlTransform: safeUrl,
    });
  } catch (error) {
    console.error("Markdown failed to render; showing the source instead.", error);
    return <RawText source={source} className={className} />;
  }

  return <div className={cn("text-base break-words", className)}>{rendered}</div>;
}

function RawText({ source, className }: { source: string; className?: string }) {
  return (
    <pre className={cn("font-sans text-base leading-7 whitespace-pre-wrap break-words", className)}>
      {source}
    </pre>
  );
}

const SAFE_PROTOCOL = /^(https?|mailto):/i;

const safeUrl: UrlTransform = (url) => {
  const value = url.trim();
  // A colon before any `/`, `?` or `#` means a scheme; anything else is relative.
  const colon = value.indexOf(":");
  const firstPathChar = value.search(/[/?#]/);
  const hasScheme = colon !== -1 && (firstPathChar === -1 || colon < firstPathChar);
  if (!hasScheme || SAFE_PROTOCOL.test(value)) return value;
  return "";
};

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
