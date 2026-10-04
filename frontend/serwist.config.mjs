// `serwist build` bundles worker/sw.ts into out/sw.js with the list of files to
// precache. Run after `next build`, which writes out/.
const config = {
  swSrc: "worker/sw.ts",
  swDest: "out/sw.js",
  globDirectory: "out",
  // Pages, styles and fonts up front. Scripts are cached as they're used
  // (worker/sw.ts): all of them would be megabytes of code highlighters.
  globPatterns: ["**/*.{html,css,svg,png,ico,woff2,txt}"],
  globIgnores: ["sw.js", "404.html"],
  maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
};

export default config;
