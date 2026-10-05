import { brandIcon } from "@/app/brand-icon";

// The app's icons, as files: the favicon and the iPhone's (app/layout.tsx),
// and the installed app's (the web app manifest). iOS rounds its own corners.
const ICONS: Record<string, [size: number, square?: boolean]> = {
  "favicon.png": [64],
  "apple-icon.png": [180, true],
  "icon-192.png": [192],
  "icon-512.png": [512],
};

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(ICONS).map((icon) => ({ icon }));
}

export async function GET(_request: Request, { params }: RouteContext<"/brand/[icon]">) {
  const [size, square] = ICONS[(await params).icon];
  return brandIcon(size, { square });
}
