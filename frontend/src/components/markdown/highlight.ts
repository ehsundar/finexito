import rehypeShikiFromHighlighter from "@shikijs/rehype/core";
import type { Root } from "hast";
import { createJavaScriptRegexEngine, getSingletonHighlighter } from "shiki";

/**
 * Code highlighting, a rehype plugin for react-markdown.
 *
 * One highlighter per page load: building it is the expensive part.
 * Languages load the first time a page uses them; a language Shiki does not know
 * (or no language at all) renders as plain, uncoloured code instead of failing.
 */
const THEMES = { light: "github-light", dark: "github-dark" } as const;

const highlighter = () =>
  getSingletonHighlighter({
    themes: Object.values(THEMES),
    langs: [],
    // Pure JavaScript, so no WebAssembly to ship.
    engine: createJavaScriptRegexEngine({ forgiving: true }),
  });

export function rehypeHighlight() {
  return async (tree: Root, file: Parameters<ReturnType<typeof rehypeShikiFromHighlighter>>[1]) => {
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
    return transformer(tree, file, () => undefined);
  };
}
