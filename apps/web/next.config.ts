import type { NextConfig } from "next";

// Server-side calls and the /api rewrite go here. In production Caddy sends /api straight to the API,
// so the rewrite only matters for `npm run dev` and the local compose stack.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  output: "standalone",
  rewrites: async () => [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }],
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
