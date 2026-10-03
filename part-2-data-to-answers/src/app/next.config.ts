import type { NextConfig } from "next";

// Production is a static export hosted on Amplify (NEXT_OUTPUT=export, see `npm run build`).
// In `next dev` the API is reached through a same-origin rewrite so the browser needs no CORS.
const isExport = process.env.NEXT_OUTPUT === "export";
const devApi = process.env.DEV_API_PROXY_TARGET;

const config: NextConfig = {
  output: isExport ? "export" : undefined,
  trailingSlash: true,
  agentRules: false, // do not generate AGENTS.md / CLAUDE.md files in this folder
  images: { unoptimized: true },
  ...(!isExport && devApi
    ? { async rewrites() { return [{ source: "/api/:path*", destination: `${devApi.replace(/\/$/, "")}/:path*` }]; } }
    : {}),
};

export default config;
