/** Global platform role. Lowercase per API contract §5 GlobalRole enum. */
export type GlobalRole = "superuser" | "manager" | "none";

/** Authenticated user info returned by the backend. Mirrors API contract §5 UserInfo. */
export interface UserInfo {
  sub: string;
  email: string;
  name: string;
  global_role: GlobalRole;
}

/** Response shape from POST /auth/google. Mirrors API contract §3.1. */
export interface GoogleAuthResponse {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  user: UserInfo;
}

/** Error body from the API. Mirrors API contract §5 ErrorBody. */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

/** Top-level error response envelope. Mirrors API contract §5 ErrorResponse. */
export interface ErrorResponse {
  error: ApiError;
}
