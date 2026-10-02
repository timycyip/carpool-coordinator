import type { NextConfig } from "next";

const nextConfig: NextConfig =
  process.env.NODE_ENV === "development"
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${
                process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
              }/:path*`,
            },
          ];
        },
      }
    : {
        output: "export",
        trailingSlash: true,
      };

export default nextConfig;
