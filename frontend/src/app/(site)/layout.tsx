"use client";

import Link from "next/link";

import { AppFrame } from "@/components/app/frame";
import { useSiteName } from "@/lib/site";

/** Pages outside the app (sign-in, dashboard, content) carry the brand header. */
export default function SiteLayout({ children }: LayoutProps<"/">) {
  const name = useSiteName();
  return (
    <AppFrame>
      <header className="px-6 pt-[calc(env(safe-area-inset-top)+1.25rem)] pb-5">
        <Link href="/" className="inline-flex items-center gap-2.5 text-lg font-medium">
          {/* The brand's mark (brand/README.md); the name is the deployment's. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/mark.svg" alt="" className="h-7 w-auto" />
          {name}
        </Link>
      </header>
      {children}
    </AppFrame>
  );
}
