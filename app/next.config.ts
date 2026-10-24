import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // The app imports Convex's generated api from ../convex, outside this folder.
  experimental: { externalDir: true },
  turbopack: { root: path.join(__dirname, "..") },
};

export default nextConfig;
