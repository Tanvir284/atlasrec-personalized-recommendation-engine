let csrfToken;
let sessionToken;
let csrfInitialization;

function readStorage(key) {
  try {
    return typeof window !== "undefined" ? window.localStorage.getItem(key) || undefined : undefined;
  } catch {
    return undefined;
  }
}

function writeStorage(key, value) {
  try {
    if (typeof window === "undefined") return;
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {}
}

function cookieCsrf() {
  if (typeof document === "undefined") return undefined;
  const cookie = document.cookie.split("; ").find(value => value.startsWith("atlas_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("atlas_csrf=".length)) : undefined;
}

function getSessionToken() {
  if (!sessionToken) sessionToken = readStorage("atlas_session_token");
  return sessionToken;
}

function setSessionToken(value) {
  sessionToken = value || undefined;
  writeStorage("atlas_session_token", sessionToken);
}

function getCsrfToken() {
  return cookieCsrf() || csrfToken || readStorage("atlas_csrf_token");
}

function setCsrfToken(value) {
  csrfToken = value || undefined;
  writeStorage("atlas_csrf_token", csrfToken);
}

async function initializeCsrf() {
  if (!csrfInitialization) {
    const activeSession = getSessionToken();
    csrfInitialization = fetch("/api/v1/auth/csrf", {
      credentials: "same-origin",
      headers: activeSession ? { "x-session-token": activeSession } : {},
    })
      .then(async response => {
        if (!response.ok) throw new Error("Could not initialize the session");
        const token = (await response.json()).csrf_token;
        setCsrfToken(token);
        return token;
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
    const activeSession = getSessionToken();
    if (activeSession) headers["x-session-token"] = activeSession;
    if (mutation) {
      let token = getCsrfToken();
      if (!token) token = await initializeCsrf();
      headers["x-csrf-token"] = token;
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
        setCsrfToken(undefined);
        await initializeCsrf();
        continue;
      }
      const error = new Error(
        typeof data.detail === "string" ? data.detail : "Check the supplied values and try again",
      );
      error.status = response.status;
      throw error;
    }
    if (data.session_token) setSessionToken(data.session_token);
    if (data.csrf_token) setCsrfToken(data.csrf_token);
    if (path === "/auth/logout") {
      setSessionToken(undefined);
      setCsrfToken(undefined);
    }
    if (path === "/me" && data && data.user === null && activeSession) {
      setSessionToken(undefined);
    }
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
