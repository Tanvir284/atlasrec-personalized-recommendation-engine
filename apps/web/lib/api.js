let csrfToken;
let csrfInitialization;
function cookieCsrf() {
  const cookie = document.cookie.split("; ").find(value => value.startsWith("atlas_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("atlas_csrf=".length)) : undefined;
}
async function initializeCsrf() {
  if (!csrfInitialization) {
    csrfInitialization = fetch("/api/v1/auth/csrf", { credentials: "same-origin" })
      .then(async response => {
        if (!response.ok) throw new Error("Could not initialize the session");
        csrfToken = (await response.json()).csrf_token;
        return csrfToken;
      })
      .finally(() => {
        csrfInitialization = undefined;
      });
  }
  return csrfInitialization;
}
export async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const mutation = !["GET", "HEAD"].includes(method);
  for (let attempt = 0; attempt < 2; attempt++) {
    const headers = { ...options.headers };
    if (mutation) {
      csrfToken = cookieCsrf();
      if (!csrfToken) await initializeCsrf();
      headers["x-csrf-token"] = csrfToken;
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch("/api/v1" + path, {
      ...options,
      method,
      headers,
      credentials: "same-origin",
    });
    let data;
    try {
      data = await response.json();
    } catch {
      const error = new Error("The service returned an incomplete response. Please try again.");
      error.status = response.ok ? 503 : response.status;
      throw error;
    }
    if (!response.ok) {
      // These errors reject the request before any mutation. Retry once with a fresh token.
      if (
        mutation &&
        attempt === 0 &&
        response.status === 403 &&
        ["Invalid CSRF token", "Session CSRF token mismatch"].includes(data.detail)
      ) {
        await initializeCsrf();
        continue;
      }
      const error = new Error(
        typeof data.detail === "string" ? data.detail : "Check the supplied values and try again",
      );
      error.status = response.status;
      throw error;
    }
    if (data.csrf_token) csrfToken = data.csrf_token;
    if (path === "/auth/logout") csrfToken = undefined;
    return data;
  }
}
export async function sendEvent(item, kind, surface, recommendation, position) {
  const body = JSON.stringify({
    id: crypto.randomUUID(),
    item_id: item,
    kind,
    surface,
    ...(recommendation ? { request_id: recommendation, position } : {}),
  });
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      return await api("/events", { method: "POST", body });
    } catch (error) {
      // Event IDs make this safe even if the first response was lost after commit.
      if (attempt || (error.status !== 503 && !(error instanceof TypeError))) throw error;
      await new Promise(resolve => setTimeout(resolve, 400));
    }
  }
}
