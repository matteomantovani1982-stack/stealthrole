/** @type {import('next').NextConfig} */
function apiRewriteTarget() {
  const fallback = "http://localhost:8000";
  const explicit = process.env.NEXT_PUBLIC_API_URL || "";
  const isDev = process.env.NODE_ENV === "development";
  const forceProd =
    process.env.NEXT_PUBLIC_FORCE_PROD_API === "1" ||
    process.env.NEXT_PUBLIC_FORCE_PROD_API === "true";

  // Footgun: shell or .env has prod API while you run `npm run dev` — all /api
  // traffic goes to prod (Anthropic billing) even on localhost:3000.
  if (isDev && explicit && !forceProd) {
    const isLocal =
      explicit.includes("localhost") || explicit.includes("127.0.0.1");
    if (!isLocal) {
      console.warn(
        "\n[next.config] NEXT_PUBLIC_API_URL points to a non-local API in development.\n" +
          `  Current value: ${explicit}\n` +
          "  Using http://localhost:8000 for rewrites instead (your Docker / local FastAPI).\n" +
          "  To proxy the dev frontend to production API instead, set NEXT_PUBLIC_FORCE_PROD_API=1\n",
      );
      return fallback;
    }
  }

  return explicit || fallback;
}

const nextConfig = {
  async rewrites() {
    const apiUrl = apiRewriteTarget();
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
