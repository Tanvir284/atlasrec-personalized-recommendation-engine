// Narrow same-origin transport proxy. All authorization and business logic live in Python.
export const dynamic = "force-dynamic";
async function proxy(request) {
  const source = new URL(request.url);
  const target = new URL(
    source.pathname + source.search,
    process.env.API_INTERNAL_URL || "http://127.0.0.1:8000",
  );
  const headers = new Headers(request.headers);
  for (const name of ["host", "connection", "content-length"]) headers.delete(name);
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      cache: "no-store",
      redirect: "manual",
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      signal: AbortSignal.timeout(15000),
    });
    const responseHeaders = new Headers(upstream.headers);
    for (const name of ["content-length", "content-encoding", "connection", "transfer-encoding"])
      responseHeaders.delete(name);
    // Finish reading inside the timeout/error boundary before sending a successful status.
    const body = await upstream.arrayBuffer();
    return new Response(body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json(
      {
        detail: "The recommendation service is unavailable. Start the API and check its readiness.",
      },
      { status: 503 },
    );
  }
}
export const GET = proxy,
  POST = proxy,
  PUT = proxy,
  DELETE = proxy,
  PATCH = proxy,
  HEAD = proxy;
