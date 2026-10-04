import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Plain files in `out/`, served by Caddy: no Node server in production. The
  // browser calls Django itself, so nothing here runs per request.
  output: "export",
  // `next dev` opened from a phone on the same network, by this machine's
  // address: without this, Next blocks its dev scripts and the page stays blank.
  allowedDevOrigins: ["192.168.*.*", "10.*.*.*", "*.local"],
};

export default nextConfig;
