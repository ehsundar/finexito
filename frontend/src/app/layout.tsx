import type { Viewport } from "next";
import { Geist_Mono, Inter } from "next/font/google";
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
      </body>
    </html>
  );
}
