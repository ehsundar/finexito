"use client";

import { notFound, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { signIn } from "@/lib/api/client";

/**
 * Development only: signs in with the tokens `manage.py login_as <email>` prints,
 * so you can be anyone locally without going through Google.
 */
export default function DevLoginPage() {
  const params = useSearchParams();
  const router = useRouter();
  const access = params.get("access");
  const refresh = params.get("refresh");

  useEffect(() => {
    if (process.env.NODE_ENV === "production" || !access || !refresh) return;
    signIn({ access, refresh }).then(() => router.replace("/dashboard"));
  }, [access, refresh, router]);

  if (process.env.NODE_ENV === "production") notFound();
  return null;
}
