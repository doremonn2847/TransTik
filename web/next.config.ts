import type { NextConfig } from "next";

// Where the FastAPI service lives. Rewrites are resolved at build time, so the Docker
// image is built with API_URL=http://api:8765 and local dev uses the default.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8765";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
