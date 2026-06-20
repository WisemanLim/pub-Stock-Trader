import type { NextConfig } from 'next';

const config: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  async rewrites() {
    const bffUrl = process.env.BFF_URL ?? 'http://localhost:3002';
    return [
      {
        source: '/bff/:path*',
        destination: `${bffUrl}/:path*`,
      },
    ];
  },
};

export default config;
