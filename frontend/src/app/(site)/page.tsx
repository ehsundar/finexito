import { ChevronRight, ListTodo } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/** The apps on offer. Each opens at its own path; signing in happens on the way. */
const APPS = [
  {
    href: "/todos",
    icon: ListTodo,
    name: "Todos",
    description: "Tasks, projects and labels, with what's due today up front.",
  },
];

/** The landing: what's here and the way in. Nothing but content. */
export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col gap-10 px-6 pt-6">
      <section className="flex flex-col gap-3">
        <h1 className="text-3xl font-medium tracking-tight">Small apps for everyday things.</h1>
        <p className="text-muted-foreground">
          A growing set of focused tools, each doing one job well. One account opens all of them.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-muted-foreground text-sm font-medium">Apps</h2>
        <ul className="flex flex-col gap-2">
          {APPS.map(({ href, icon: Icon, name, description }) => (
            <li key={href}>
              <Link href={href} className="hover:bg-muted flex items-center gap-4 rounded-xl border p-4">
                <span className="bg-primary/10 text-primary flex size-11 shrink-0 items-center justify-center rounded-lg">
                  <Icon className="size-5" />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="font-medium">{name}</span>
                  <span className="text-muted-foreground text-sm">{description}</span>
                </span>
                <ChevronRight className="text-muted-foreground size-5 shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
        <p className="text-muted-foreground text-sm">More are on the way.</p>
      </section>

      <section className="bg-background/95 sticky bottom-0 -mx-6 mt-auto flex flex-col gap-2 border-t px-6 pt-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] backdrop-blur">
        <Button size="lg" nativeButton={false} render={<Link href="/login" />}>
          Sign in or create an account
        </Button>
        <p className="text-muted-foreground text-center text-xs">With your Google account.</p>
      </section>
    </main>
  );
}
