import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Plain files in `out/`, served by Caddy: no Node server in production. The
  // browser calls Django itself, so nothing here runs per request.
  output: "export",
};

export default nextConfig;
