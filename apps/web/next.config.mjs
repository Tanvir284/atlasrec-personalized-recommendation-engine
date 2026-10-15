export default {
  ...(process.env.NEXT_STANDALONE === "1" ? { output: "standalone" } : {}),
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: { cpus: 2, staticGenerationMaxConcurrency: 2, webpackMemoryOptimizations: true },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'self' https://huggingface.co https://*.hf.space",
          },
        ],
      },
    ];
  },
};
