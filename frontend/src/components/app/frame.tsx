"use client";

import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The app's phone-sized column. Wider screens get the same column, centred,
 * so every screen is designed once, for the phone.
 */
export function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 justify-center sm:bg-muted">
      <div className="bg-background relative flex min-h-dvh w-full max-w-md flex-col sm:border-x">
        {children}
      </div>
    </div>
  );
}

/** A screen's top bar: back, a title (or anything in its place) and actions. */
export function AppBar({
  title,
  back,
  actions,
  children,
}: {
  title?: React.ReactNode;
  /** Where the back arrow goes; none on a tab's own screen. */
  back?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <header className="bg-background/90 sticky top-0 z-20 flex min-h-14 items-center gap-1 px-2 pt-[env(safe-area-inset-top)] backdrop-blur">
      {back ? (
        <Button variant="ghost" size="icon-lg" aria-label="Back" nativeButton={false} render={<Link href={back} />}>
          <ChevronLeft className="size-5" />
        </Button>
      ) : (
        <span className="w-2" />
      )}
      {children ?? (
        <h1 className="flex min-w-0 flex-1 items-center gap-2 text-lg font-medium">{title}</h1>
      )}
      {actions && <div className="flex items-center">{actions}</div>}
    </header>
  );
}

/** A screen's scrolling body, clear of the tab bar. */
export function Screen({ className, ...props }: React.ComponentProps<"main">) {
  return <main className={cn("flex flex-1 flex-col gap-6 px-4 pt-2 pb-28", className)} {...props} />;
}

/** The bottom tabs, with an optional floating action above them. */
export function TabBar({ action, children }: { action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <nav className="bg-background/95 sticky bottom-0 z-20 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur">
      {action && <div className="absolute right-4 bottom-full mb-4">{action}</div>}
      <ul className="flex h-16">{children}</ul>
    </nav>
  );
}

export function Tab({
  href,
  icon,
  label,
  match = [],
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  /** Other paths that belong to this tab. */
  match?: string[];
}) {
  const pathname = usePathname();
  const active = pathname === href || match.some((path) => pathname.startsWith(path));
  return (
    <li className="flex-1">
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "text-muted-foreground flex h-full flex-col items-center justify-center gap-1 text-xs [&_svg]:size-5",
          active && "text-primary font-medium",
        )}
      >
        {icon}
        {label}
      </Link>
    </li>
  );
}

/** The screen's main action, floating above the tab bar. */
export function Fab({ className, ...props }: React.ComponentProps<typeof Button>) {
  return (
    <Button
      className={cn("size-14 rounded-full shadow-lg [&_svg:not([class*='size-'])]:size-6", className)}
      {...props}
    />
  );
}
