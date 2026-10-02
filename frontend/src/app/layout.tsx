import type { Metadata } from "next";
import Link from "next/link";
import { Geist_Mono, Inter } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { getSite } from "@/lib/site";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const { name } = await getSite();
  return { title: { default: name, template: `%s · ${name}` } };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const { name } = await getSite();
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="px-6 py-5">
          <Link href="/" className="inline-flex items-center gap-2.5 text-lg font-medium">
            {/* The brand's mark (brand/README.md); the name is the deployment's. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/mark.svg" alt="" className="h-7 w-auto" />
            {name}
          </Link>
        </header>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
