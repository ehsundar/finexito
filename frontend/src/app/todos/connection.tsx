"use client";

import { CloudOff } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";
import { toast } from "sonner";

import { offlineFetch, start, sync, syncState } from "@/app/todos/offline";
import { handleOffline } from "@/lib/api/client";

// Before the shell's first queries, so the app opens with no connection.
if (typeof window !== "undefined") handleOffline(offlineFetch);

/**
 * Keeps the todos client working offline: answers calls from the local copy
 * when the server can't be reached, syncs on opening, on focus, on reconnecting
 * and every minute, and installs the service worker. Shows a line while offline
 * or while changes wait.
 */
export function Connection() {
  const { online, waiting } = useSyncExternalStore(syncState.subscribe, syncState.get, syncState.server);

  useEffect(() => {
    void start();
    const again = () => void sync();
    const visible = () => document.visibilityState === "visible" && again();
    window.addEventListener("online", again);
    document.addEventListener("visibilitychange", visible);
    const timer = setInterval(again, 60_000);
    return () => {
      window.removeEventListener("online", again);
      document.removeEventListener("visibilitychange", visible);
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    // A new version waits until the member reloads into it.
    const offer = (worker: ServiceWorker) =>
      toast("Update available", {
        duration: Infinity,
        action: { label: "Reload", onClick: () => worker.postMessage("skip-waiting") },
      });
    navigator.serviceWorker.register("/sw.js").then((registration) => {
      if (registration.waiting && navigator.serviceWorker.controller) offer(registration.waiting);
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", () => {
          if (worker.state === "installed" && navigator.serviceWorker.controller) offer(worker);
        });
      });
    });
    let reloaded = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!reloaded) location.reload();
      reloaded = true;
    });
  }, []);

  if (online && !waiting) return null;
  return (
    <div role="status" className="bg-muted text-muted-foreground flex items-center justify-center gap-2 px-4 py-1.5 text-xs">
      {!online && <CloudOff className="size-3.5" />}
      {online ? "Syncing" : "Offline"}
      {waiting > 0 && ` · ${waiting} change${waiting > 1 ? "s" : ""} waiting`}
    </div>
  );
}
