import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // dev-only: allows the dev server's HMR/Fast Refresh channel when the
  // app is opened via 127.0.0.1 rather than localhost (Next 16 treats
  // them as different origins by default and silently blocks dev
  // resources otherwise -- this was the root cause of a client
  // component failing to hydrate during local testing).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Self-contained `.next/standalone` build (server + only the deps it
  // actually uses) so the Docker image (see frontend/Dockerfile) doesn't
  // need to ship node_modules or run `npm install` at container build time.
  output: "standalone",
};

export default nextConfig;
