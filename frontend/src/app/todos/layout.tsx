import type { Metadata } from "next";

import { Shell } from "@/app/todos/shell";

export const metadata: Metadata = { title: { default: "Todos", template: "%s · Todos" } };

export default function TodosLayout({ children }: LayoutProps<"/todos">) {
  return <Shell>{children}</Shell>;
}
