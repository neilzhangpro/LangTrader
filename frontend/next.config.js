/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // API 代理（WebSocket 由前端直接连接，无需 rewrite）
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/:path*`,
      },
    ]
  },
}

module.exports = nextConfig

