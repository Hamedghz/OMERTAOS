import path from "node:path";
import { fileURLToPath } from "node:url";

const nextConfig = {
  // Include local workspace packages without inferring a root from host lockfiles.
  outputFileTracingRoot: path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
  transpilePackages: ["@aion/ui-core"],
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },
  webpack: (config) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
    };
    return config;
  },
};

export default nextConfig;
