import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getDevUserId(): string {
  if (typeof window !== "undefined") {
    return (
      localStorage.getItem("dev_user_id") ??
      process.env.NEXT_PUBLIC_DEV_USER_ID ??
      "dev-user-1"
    );
  }
  return process.env.NEXT_PUBLIC_DEV_USER_ID ?? "dev-user-1";
}

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// In development, inject X-Dev-User-Id on every request.
if (process.env.NODE_ENV !== "production") {
  apiClient.interceptors.request.use((config) => {
    config.headers["X-Dev-User-Id"] = getDevUserId();
    return config;
  });
}

/** Thin helper for SSE fetch calls (axios doesn't support ReadableStream). */
export function ssePost(path: string, body: unknown): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(process.env.NODE_ENV !== "production"
        ? { "X-Dev-User-Id": getDevUserId() }
        : {}),
    },
    body: JSON.stringify(body),
  });
}
