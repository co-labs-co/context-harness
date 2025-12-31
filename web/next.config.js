/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Export as static HTML/CSS/JS
  output: 'export',
  // Disable image optimization (not supported in static export)
  images: {
    unoptimized: true,
  },
  // Use relative paths for assets
  assetPrefix: process.env.NODE_ENV === 'production' ? '' : undefined,
  trailingSlash: true,
};

module.exports = nextConfig;
