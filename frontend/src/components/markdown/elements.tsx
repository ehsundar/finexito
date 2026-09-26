import Link from "next/link";
import type { ComponentProps, ComponentType } from "react";
import type { Components, ExtraProps } from "react-markdown";

import { CopyButton } from "@/components/markdown/copy-button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

/**
 * One component per element the Markdown can produce. Anything not listed here
 * cannot appear: raw HTML is turned into text before rendering (see markdown.tsx).
 */
type Props<T extends keyof React.JSX.IntrinsicElements> = ComponentProps<T>;

/** react-markdown passes its syntax-tree `node` to every component; the DOM must not get it. */
function withoutNode<P extends object>(Component: ComponentType<P>) {
  function Stripped(props: P & ExtraProps) {
    const rest = { ...props };
    delete rest.node;
    return <Component {...rest} />;
  }
  Stripped.displayName = Component.displayName ?? Component.name;
  return Stripped;
}

const heading = {
  h1: "mt-10 mb-4 text-3xl font-semibold tracking-tight",
  h2: "mt-10 mb-4 border-b pb-2 text-2xl font-semibold tracking-tight",
  h3: "mt-8 mb-3 text-xl font-semibold tracking-tight",
  h4: "mt-6 mb-2 text-lg font-semibold",
  h5: "mt-6 mb-2 text-base font-semibold",
  h6: "text-muted-foreground mt-6 mb-2 text-sm font-semibold uppercase tracking-wide",
} as const;

function makeHeading(Tag: keyof typeof heading) {
  function Heading({ className, ...props }: Props<typeof Tag>) {
    return <Tag className={cn(heading[Tag], "scroll-m-20 first:mt-0", className)} {...props} />;
  }
  Heading.displayName = `Markdown.${Tag}`;
  return Heading;
}

function Paragraph({ className, ...props }: Props<"p">) {
  return <p className={cn("my-4 leading-7 first:mt-0 last:mb-0", className)} {...props} />;
}

/** Same-site links navigate client-side; everything else opens in a new tab. */
function Anchor({ className, href = "", children, ...props }: Props<"a">) {
  const classes = cn("text-primary font-medium underline underline-offset-4", className);
  const internal = (href.startsWith("/") && !href.startsWith("//")) || href.startsWith("#");

  if (internal) {
    return (
      <Link href={href} className={classes} {...props}>
        {children}
      </Link>
    );
  }
  return (
    <a
      href={href || undefined}
      className={classes}
      target="_blank"
      rel="noopener noreferrer nofollow"
      {...props}
    >
      {children}
    </a>
  );
}

function Blockquote({ className, ...props }: Props<"blockquote">) {
  return (
    <blockquote
      className={cn("text-muted-foreground my-6 border-l-2 pl-4 italic", className)}
      {...props}
    />
  );
}

function UnorderedList({ className, ...props }: Props<"ul">) {
  // Task lists (`- [ ]`) carry their own checkbox, so they lose the bullet.
  const isTaskList = className?.includes("contains-task-list");
  return (
    <ul
      className={cn(
        "my-4 ml-6 space-y-2 [&_ol]:my-2 [&_ul]:my-2",
        isTaskList ? "ml-1 list-none" : "list-disc",
        className,
      )}
      {...props}
    />
  );
}

function OrderedList({ className, ...props }: Props<"ol">) {
  return (
    <ol
      className={cn("my-4 ml-6 list-decimal space-y-2 [&_ol]:my-2 [&_ul]:my-2", className)}
      {...props}
    />
  );
}

function ListItem({ className, ...props }: Props<"li">) {
  return <li className={cn("leading-7 [&>p]:my-1", className)} {...props} />;
}

/** Only ever a task-list checkbox: GFM emits no other inputs, and raw HTML is text. */
function Checkbox({ checked, className }: Props<"input">) {
  return (
    <input
      type="checkbox"
      checked={Boolean(checked)}
      readOnly
      disabled
      aria-label={checked ? "Done" : "Not done"}
      className={cn("accent-primary mr-2 size-4 translate-y-0.5", className)}
    />
  );
}

function InlineCode({ className, ...props }: Props<"code">) {
  return (
    <code
      className={cn(
        "bg-muted rounded px-[0.3rem] py-[0.2rem] font-mono text-[0.875em] break-words",
        className,
      )}
      {...props}
    />
  );
}

/**
 * A fenced block. It scrolls sideways rather than widen the page on a phone.
 * The copy button shows on hover with a mouse, and always on touch screens.
 */
function CodeBlock({ className, ...props }: Props<"pre">) {
  return (
    <div className="group relative my-6">
      <pre
        className={cn(
          "bg-muted overflow-x-auto rounded-lg border p-4 pr-12 font-mono text-sm leading-6",
          "[&>code]:bg-transparent [&>code]:p-0 [&>code]:text-[inherit] [&>code]:break-normal",
          className,
        )}
        {...props}
      />
      <CopyButton className="absolute top-2 right-2 opacity-100 transition-opacity focus-visible:opacity-100 pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100" />
    </div>
  );
}

function Image({ className, alt = "", src, ...props }: Props<"img">) {
  if (!src) return null;
  return (
    // Authors link images from anywhere, so next/image's allow-list does not fit.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={typeof src === "string" ? src : undefined}
      alt={alt}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      className={cn("my-6 h-auto max-w-full rounded-lg border", className)}
      {...props}
    />
  );
}

function Rule({ className, ...props }: Props<"hr">) {
  return <hr className={cn("my-8", className)} {...props} />;
}

function MarkdownTable({ className, ...props }: Props<"table">) {
  return (
    <div className="my-6 rounded-lg border">
      <Table className={className} {...props} />
    </div>
  );
}

/** Cells wrap, so a wide table scrolls only when it truly has to. */
function Cell({ className, ...props }: Props<"td">) {
  return <TableCell className={cn("whitespace-normal", className)} {...props} />;
}

export const markdownComponents: Components = {
  h1: withoutNode(makeHeading("h1")),
  h2: withoutNode(makeHeading("h2")),
  h3: withoutNode(makeHeading("h3")),
  h4: withoutNode(makeHeading("h4")),
  h5: withoutNode(makeHeading("h5")),
  h6: withoutNode(makeHeading("h6")),
  p: withoutNode(Paragraph),
  a: withoutNode(Anchor),
  blockquote: withoutNode(Blockquote),
  ul: withoutNode(UnorderedList),
  ol: withoutNode(OrderedList),
  li: withoutNode(ListItem),
  input: withoutNode(Checkbox),
  code: withoutNode(InlineCode),
  pre: withoutNode(CodeBlock),
  img: withoutNode(Image),
  hr: withoutNode(Rule),
  table: withoutNode(MarkdownTable),
  thead: withoutNode(TableHeader),
  tbody: withoutNode(TableBody),
  tr: withoutNode(TableRow),
  th: withoutNode(TableHead),
  td: withoutNode(Cell),
};
