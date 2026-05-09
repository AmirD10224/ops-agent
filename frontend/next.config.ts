import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: { typedRoutes: true },
  // The Modal-deployed API URL is read from NEXT_PUBLIC_API_URL at build time.
};

export default nextConfig;
