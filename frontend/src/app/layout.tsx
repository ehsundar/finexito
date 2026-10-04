import type { Metadata, Viewport } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import { RotateCcw } from "lucide-react";
import { Suspense } from "react";

import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// The app reaches under the notch and home bar; screens pad by the safe areas.
export const viewport: Viewport = { viewportFit: "cover" };

// Installable on a phone. The manifest is one of the site's own files, as iOS
// wants; Caddy writes this deployment's name into it (deploy/Caddyfile).
export const metadata: Metadata = {
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* Pages read the query string (useSearchParams), which a static export
            only knows in the browser. */}
        <Suspense>{children}</Suspense>
        <Toaster position="top-center" />
        <div className="fixed inset-0 z-[100] hidden flex-col items-center justify-center gap-3 bg-background p-6 text-center phone-landscape:flex">
          <RotateCcw className="size-8 text-muted-foreground" />
          <p className="font-medium">Turn your phone upright to carry on.</p>
        </div>
      </body>
    </html>
  );
}
