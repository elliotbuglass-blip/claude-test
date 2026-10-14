import type { NextConfig } from "next";

const config: NextConfig = {
  // imapflow and mailparser use Node built-ins; keep them out of the bundle.
  serverExternalPackages: ["imapflow", "mailparser", "nodemailer"],
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Private dashboard: never indexed, never framed.
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
        ],
      },
    ];
  },
};

export default config;
