import { redirect } from "next/navigation";

import { currentUser } from "@/lib/auth/current-user";

export default async function HomePage() {
  redirect((await currentUser()) ? "/dashboard" : "/login");
}
