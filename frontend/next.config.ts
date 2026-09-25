import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a self-contained server in .next/standalone, so the production image
  // ships without node_modules or the build toolchain.
  output: "standalone",
};

export default nextConfig;
