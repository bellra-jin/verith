import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  logging: { incomingRequests: { ignore: [/\/api\/auth\/callback/] } },
};

export default nextConfig;
