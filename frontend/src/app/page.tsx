"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <main
        className="flex flex-1 flex-col items-center justify-center px-4"
        aria-busy="true"
      >
        <p className="text-muted-foreground">Loading...</p>
      </main>
    );
  }

  if (isAuthenticated) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-4">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Welcome back, {user?.name}
        </h1>
        <p className="mt-2 text-muted-foreground">
          Ready to coordinate your next carpool.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
        >
          Go to dashboard
        </Link>
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4">
      <h1 className="text-3xl font-semibold tracking-tight text-foreground">
        Carpool Coordinator
      </h1>
      <p className="mt-3 max-w-md text-center text-muted-foreground">
        Coordinate carpools for your event — drivers, passengers, one shared
        session code.
      </p>
      <button
        type="button"
        disabled
        className="mt-6 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground opacity-50 transition-colors"
      >
        Sign in with Google
      </button>
      <p className="mt-2 text-xs text-muted-foreground">
        Google sign-in available soon.
      </p>
    </main>
  );
}
