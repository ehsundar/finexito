import ReactMarkdown, { type UrlTransform } from "react-markdown";

/**
 * One line of inline Markdown (bold, italic, code, links), for task titles.
 * Anything else, block elements and raw HTML included, renders as its text.
 * Synchronous, so it works in client components too.
 */
export function InlineMarkdown({ source }: { source: string }) {
  return (
    <ReactMarkdown
      allowedElements={["strong", "em", "code", "a", "del"]}
      unwrapDisallowed
      skipHtml
      urlTransform={safeUrl}
      components={{
        code: ({ children }) => (
          <code className="bg-muted rounded px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2"
            onClick={(event) => event.stopPropagation()}
          >
            {children}
          </a>
        ),
      }}
    >
      {source}
    </ReactMarkdown>
  );
}

const SAFE_PROTOCOL = /^(https?|mailto):/i;

export const safeUrl: UrlTransform = (url) => {
  const value = url.trim();
  // A colon before any `/`, `?` or `#` means a scheme; anything else is relative.
  const colon = value.indexOf(":");
  const firstPathChar = value.search(/[/?#]/);
  const hasScheme = colon !== -1 && (firstPathChar === -1 || colon < firstPathChar);
  if (!hasScheme || SAFE_PROTOCOL.test(value)) return value;
  return "";
};
