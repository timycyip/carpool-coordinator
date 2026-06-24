import type { ErrorResponse } from "./types";

let authToken: string | null = null;
const unauthorizedListeners = new Set<() => void>();

/** Store the JWT token in the module-scoped holder. Called by AuthProvider on login. */
export function setAuthToken(token: string): void {
  authToken = token;
}

/** Clear the JWT token from the module-scoped holder. Called on logout and 401. */
export function clearAuthToken(): void {
  authToken = null;
}

/** Return the current module-scoped JWT token, or null if unauthenticated. */
export function getAuthToken(): string | null {
  return authToken;
}

/**
 * Register a callback invoked when the api-client receives a 401 response.
 * Returns an unsubscribe function (suitable for React useEffect cleanup).
 *
 * Used by AuthProvider to sync React state when the server revokes a session.
 * See ADR-0009 for the full design rationale.
 */
export function onUnauthorized(cb: () => void): () => void {
  unauthorizedListeners.add(cb);
  return () => {
    unauthorizedListeners.delete(cb);
  };
}

/** Error thrown by the api-client for non-2xx responses. Mirrors the backend ErrorResponse shape. */
class ApiError extends Error {
  /** Stable machine-readable error code (e.g., "VALIDATION_ERROR", "UNAUTHORIZED"). */
  code: string;
  /** Optional structured details from the backend error response. */
  details?: Record<string, unknown>;

  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
  }
}

export { ApiError };

const BASE = "/api";

/**
 * Core request function. Sends a same-origin fetch to `/api/<path>` with JSON headers
 * and optional Authorization header. Parses nested ErrorResponse on non-2xx.
 * On 401, clears the token and notifies all onUnauthorized subscribers.
 *
 * @throws {ApiError} For any non-2xx response.
 */
async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    if (res.status === 401) {
      clearAuthToken();
      for (const cb of unauthorizedListeners) {
        cb();
      }
    }

    let errorBody: ErrorResponse | undefined;
    try {
      errorBody = (await res.json()) as ErrorResponse;
    } catch {
      // response is not JSON
    }

    if (errorBody?.error) {
      throw new ApiError(
        errorBody.error.code,
        errorBody.error.message,
        errorBody.error.details,
      );
    }

    throw new ApiError("UNKNOWN_ERROR", `Request failed with status ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

/** Send a GET request to the backend API. */
export function get<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

/** Send a POST request to the backend API with a JSON body. */
export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, body);
}

/** Send a PATCH request to the backend API with a JSON body. */
export function patch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PATCH", path, body);
}

/** Send a DELETE request to the backend API. Returns undefined for 204 No Content. */
export function del(path: string): Promise<void> {
  return request<void>("DELETE", path);
}
