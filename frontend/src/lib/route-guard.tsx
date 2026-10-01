"use client";

import { redirect } from "next/navigation";
import { useAuth } from "./auth-context";

/**
 * Route guard component. Redirects to /login when the user is not authenticated.
 * Shows an aria-busy loading state while auth resolution is in progress.
 * Wrap protected pages in this component to enforce authentication.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center" aria-busy="true">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    redirect("/login");
  }

  return <>{children}</>;
}
