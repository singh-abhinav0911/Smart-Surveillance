import { BASE } from "./theme";

const TIMEOUT_MS = 8000;

async function request(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(BASE + url, { ...options, signal: controller.signal });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new ApiError(res.status, text || res.statusText, url);
    }

    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new ApiError(res.status, "Non-JSON response", url);
    }

    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") throw new ApiError(408, "Request timed out", url);
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, err.message || "Network error", url);
  } finally {
    clearTimeout(timer);
  }
}

export class ApiError extends Error {
  constructor(status, message, url) {
    super(message);
    this.status = status;
    this.url    = url;
    this.name   = "ApiError";
  }
}

async function withRetry(fn, retries = 2, delayMs = 500) {
  let lastErr;
  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) throw err;
      if (i < retries) await new Promise(r => setTimeout(r, delayMs * (i + 1)));
    }
  }
  throw lastErr;
}

const get  = (url)       => withRetry(() => request(url));
const post = (url, body) => withRetry(() => request(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
}));

export const api = {
  stats:      () => get("/api/stats"),
  health:     () => get("/api/health"),
  violations: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return get(`/api/violations${q ? "?" + q : ""}`);
  },
  violCount:  () => get("/api/violations/count"),
  cameras:    () => get("/cameras"),
};