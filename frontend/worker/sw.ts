/// <reference lib="webworker" />
// The service worker, bundled by `serwist build` (serwist.config.mjs) after the
// static export: it precaches the exported pages and bundles so the app opens
// with no connection. The API isn't cached here; the todos client keeps its own
// copy of the member's data (src/app/todos/offline.ts).
import { CacheFirst, ExpirationPlugin, Serwist, type PrecacheEntry } from "serwist";

declare const self: ServiceWorkerGlobalScope & { __SW_MANIFEST: (PrecacheEntry | string)[] };

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  precacheOptions: {
    // /todos/project?id=… is out/todos/project.html.
    cleanURLs: true,
    ignoreURLParametersMatching: [/.*/],
  },
  clientsClaim: true,
  runtimeCaching: [
    {
      // Next's hashed bundles never change, so once fetched they're kept.
      matcher: ({ url }) => url.pathname.startsWith("/_next/static/"),
      handler: new CacheFirst({
        cacheName: "next-static",
        plugins: [new ExpirationPlugin({ maxEntries: 400, maxAgeSeconds: 60 * 60 * 24 * 60 })],
      }),
    },
  ],
});

// A new version waits until the page asks for it ("Update available — reload").
self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});

serwist.addEventListeners();
