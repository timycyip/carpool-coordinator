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
          href="/register"
          className="mt-6 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
        >
          Join a session
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
      <Link
        href="/login"
        className="mt-6 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
      >
        Sign in with Google
      </Link>
    </main>
  );
}
