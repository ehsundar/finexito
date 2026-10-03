"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { getSession } from "@/lib/auth/session";

export default function HomePage() {
  const router = useRouter();
  useEffect(() => router.replace(getSession() ? "/dashboard" : "/login"), [router]);
  return null;
}
