import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // Behind Caddy this server only knows its bind address (0.0.0.0:3000), so a
    // URL built from the incoming request points there, not at the public
    // domain. Pages and route handlers redirect with `redirect()` from
    // next/navigation, which sends a relative Location. (proxy.ts sees the real
    // host, so it is exempt.)
    files: ["src/app/**"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "MemberExpression[property.name='origin'][object.property.name='nextUrl']",
          message: "request.nextUrl.origin is 0.0.0.0:3000 in production; use redirect().",
        },
        {
          selector: "NewExpression[callee.name='URL'] > MemberExpression[property.name='url']",
          message: "request.url is 0.0.0.0:3000 in production; use redirect().",
        },
        {
          selector: "CallExpression[callee.object.name='NextResponse'][callee.property.name='redirect']",
          message: "Use redirect() from next/navigation: it sends a relative Location.",
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
