import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // Old IA → unified Research entry. Temporary redirects so bookmarks
      // / external links still resolve. Drop after one release.
      { source: "/topics", destination: "/research", permanent: false },
      { source: "/domains", destination: "/research", permanent: false },
      {
        source: "/domains/trends",
        destination: "/research/trends",
        permanent: false,
      },
      // Admin → Settings rename.
      { source: "/admin", destination: "/settings", permanent: false },
      {
        source: "/admin/calibration",
        destination: "/settings/scoring",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
