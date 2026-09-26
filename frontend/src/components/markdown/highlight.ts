import "server-only";

import rehypeShikiFromHighlighter from "@shikijs/rehype/core";
import { createJavaScriptRegexEngine, getSingletonHighlighter } from "shiki";

/**
 * Code highlighting, done on the server so the browser receives coloured HTML
 * and no highlighter JavaScript.
 *
 * One highlighter per server process: building it is the expensive part.
 * Languages load the first time a page uses them; a language Shiki does not know
 * (or no language at all) renders as plain, uncoloured code instead of failing.
 */
const THEMES = { light: "github-light", dark: "github-dark" } as const;

const highlighter = () =>
  getSingletonHighlighter({
    themes: Object.values(THEMES),
    langs: [],
    // Pure JavaScript, so no WebAssembly to ship in the standalone build.
    engine: createJavaScriptRegexEngine({ forgiving: true }),
  });

export async function rehypeHighlight() {
  const transformer = rehypeShikiFromHighlighter(await highlighter(), {
    themes: THEMES,
    // Colours come from CSS variables; globals.css picks the set for the theme.
    defaultColor: false,
    lazy: true,
    defaultLanguage: "text",
    fallbackLanguage: "text",
    addLanguageClass: true,
    onError: (error) => console.error("Code highlighting failed; showing plain code.", error),
  });
  return () => transformer;
}
