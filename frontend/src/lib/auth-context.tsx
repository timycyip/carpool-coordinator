"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { post, setAuthToken, clearAuthToken, onUnauthorized } from "./api-client";
import type { GoogleAuthResponse, UserInfo } from "./types";

interface AuthContextValue {
  user: UserInfo | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (idToken: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * React context providing authentication state and actions.
 *
 * - `user` / `token`: current authenticated user info and JWT, or null.
 * - `isAuthenticated`: derived from token !== null.
 * - `isLoading`: true during the login API call (consumers show aria-busy skeletons).
 * - `login(idToken)`: exchanges a Google ID token for an app session JWT via POST /auth/google.
 * - `logout()`: clears token and user from both React state and the api-client module holder.
 *
 * Subscribes to `onUnauthorized` on mount to react to 401 responses (ADR-0009).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (idToken: string) => {
    setIsLoading(true);
    try {
      const res = await post<GoogleAuthResponse>("/auth/google", { id_token: idToken });
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    return onUnauthorized(() => {
      setToken(null);
      setUser(null);
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: token !== null,
      isLoading,
      login,
      logout,
    }),
    [user, token, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Access the auth context. Must be called inside an `<AuthProvider>`.
 *
 * @throws If used outside an AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
