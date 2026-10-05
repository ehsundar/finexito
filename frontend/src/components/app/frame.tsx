"use client";

import { ChevronLeft, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, use } from "react";

import { useProfileTheme } from "@/components/app/theme";
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
  if (use(ActiveTabContext)?.noAppBar) return null;
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

/** A screen's scrolling body, clear of the tab bar (and of the notch, with no top bar). */
export function Screen({ className, ...props }: React.ComponentProps<"main">) {
  const noAppBar = use(ActiveTabContext)?.noAppBar;
  return (
    <main
      className={cn(
        "flex flex-1 flex-col gap-6 px-4 pt-2 pb-28",
        noAppBar && "pt-[calc(env(safe-area-inset-top)+0.5rem)]",
        className,
      )}
      {...props}
    />
  );
}

export type Tab = {
  href: string;
  icon: React.ReactNode;
  label: string;
  /** A count beside the icon. */
  badge?: number;
  /** Other paths that belong to this tab. */
  match?: string[];
  /** Leave out the top bar on this tab's screens. */
  noAppBar?: boolean;
  /** Leave out the floating action on this tab's screens. */
  noFab?: boolean;
};

/** The Me tab: always last, with its own icon and label. */
export type MeTab = Omit<Tab, "icon" | "label">;

const ActiveTabContext = createContext<Tab | undefined>(undefined);

/**
 * A mini app's frame: its screens, the bottom tabs and the floating action.
 * Two to four tabs of its own, then Me (the account and the app's settings),
 * so three to five in all.
 */
export function AppShell({
  tabs,
  me,
  fab,
  children,
}: {
  tabs: [Tab, Tab] | [Tab, Tab, Tab] | [Tab, Tab, Tab, Tab];
  me: MeTab;
  /** The main action, floating above the tabs. */
  fab?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  // Every signed-in app follows the theme saved in the profile.
  useProfileTheme();
  const all: Tab[] = [...tabs, { icon: <UserRound />, label: "Me", ...me }];
  const active = all.find((tab) => pathname === tab.href || tab.match?.some((path) => pathname.startsWith(path)));
  return (
    <ActiveTabContext value={active}>
      <AppFrame>
        {children}
        <nav className="bg-background/95 sticky bottom-0 z-20 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur">
          {fab && !active?.noFab && <div className="absolute right-4 bottom-full mb-4">{fab}</div>}
          <ul className="flex h-16">
            {all.map((tab) => (
              <TabLink key={tab.href} tab={tab} active={tab === active} />
            ))}
          </ul>
        </nav>
      </AppFrame>
    </ActiveTabContext>
  );
}

function TabLink({ tab, active }: { tab: Tab; active: boolean }) {
  return (
    <li className="flex-1">
      <Link
        href={tab.href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "text-muted-foreground flex h-full flex-col items-center justify-center gap-1 text-xs [&_svg]:size-5",
          active && "text-primary font-medium",
        )}
      >
        <span className="relative">
          {tab.icon}
          {tab.badge != null && (
            <span className="bg-primary text-primary-foreground absolute -top-1.5 left-3.5 min-w-4 rounded-full px-1 text-[10px] leading-4 font-medium tabular-nums">
              {tab.badge}
            </span>
          )}
        </span>
        {tab.label}
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
