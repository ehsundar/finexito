import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

/** Rows grouped in a card, with an optional heading and heading action. */
export function List({
  title,
  action,
  className,
  children,
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("flex flex-col gap-1.5", className)}>
      {(title || action) && (
        <div className="text-muted-foreground flex min-h-7 items-center justify-between px-4 text-xs font-medium">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      <ul className="bg-card divide-y overflow-hidden rounded-xl border">{children}</ul>
    </section>
  );
}

/**
 * One row: a link (`href`), a button (`onClick`) or plain. `trailing` sits
 * outside the tappable part, for a row's own button.
 */
export function ListRow({
  href,
  onClick,
  icon,
  detail,
  trailing,
  destructive,
  indent = 0,
  className,
  children,
}: {
  href?: string;
  onClick?: () => void;
  icon?: React.ReactNode;
  /** Quiet text at the end: a count, the current value. */
  detail?: React.ReactNode;
  trailing?: React.ReactNode;
  destructive?: boolean;
  indent?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const body = (
    <>
      {icon && <span className="flex size-5 shrink-0 items-center justify-center [&_svg]:size-4">{icon}</span>}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {detail != null && <span className="text-muted-foreground truncate text-sm tabular-nums">{detail}</span>}
      {href && <ChevronRight className="text-muted-foreground size-4 shrink-0" />}
    </>
  );
  const style = cn(
    "flex min-h-12 min-w-0 flex-1 items-center gap-3 py-2 pr-4 text-left",
    (href || onClick) && "active:bg-accent hover:bg-accent/50 transition-colors",
    destructive && "text-destructive",
  );
  const padding = { paddingLeft: `${1 + indent * 1.25}rem` };
  return (
    <li className={cn("flex items-center", className)}>
      {href ? (
        <Link href={href} className={style} style={padding}>
          {body}
        </Link>
      ) : onClick ? (
        <button type="button" onClick={onClick} className={style} style={padding}>
          {body}
        </button>
      ) : (
        <div className={style} style={padding}>
          {body}
        </div>
      )}
      {trailing && <span className="flex shrink-0 items-center pr-2">{trailing}</span>}
    </li>
  );
}
