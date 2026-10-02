"use client";

import { Suspense, useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ApiError, get } from "@/lib/api-client";

type SessionSummary = {
  session_code: string;
  title: string;
  description: string | null;
  trip_mode: "to_destination" | "from_origin";
  earliest_pickup: string;
  latest_arrival: string;
  registration_deadline: string;
  status: string;
};

function displayDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "SESSION_CODE_NOT_FOUND") return "Session not found. Check the code and try again.";
    if (error.code === "REGISTRATION_CLOSED") return "Registration for this session is closed.";
    if (error.code === "FORBIDDEN") return "Sign in with an account that can access this session.";
    if (error.code === "UNAUTHORIZED") return "Sign in to view this session.";
    return error.message;
  }
  return "We could not load this session. Check your connection and try again.";
}

function RegisterContent({ linkedCode }: { linkedCode: string }) {
  const [code, setCode] = useState(linkedCode);
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const lookup = useCallback(async (sessionCode: string) => {
    setIsLoading(true);
    setError(null);
    setSession(null);
    try {
      const result = await get<SessionSummary>(
        `/sessions/${encodeURIComponent(sessionCode)}`,
      );
      setSession(result);
    } catch (lookupError) {
      setError(errorMessage(lookupError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!linkedCode) return;
    const timer = window.setTimeout(() => void lookup(linkedCode), 0);
    return () => window.clearTimeout(timer);
  }, [linkedCode, lookup]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedCode = code.trim().toUpperCase();
    setCode(normalizedCode);
    if (!normalizedCode) {
      setSession(null);
      setError("Enter a session code to continue.");
      return;
    }
    void lookup(normalizedCode);
  }

  return (
    <main className="relative flex flex-1 items-center justify-center overflow-hidden px-5 py-14 sm:px-8">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_15%_15%,rgba(5,150,105,0.12),transparent_42%),radial-gradient(ellipse_at_90%_85%,rgba(14,116,144,0.10),transparent_38%)]" />
      <section className="relative w-full max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary">
          Your ride starts here
        </p>
        <h1 className="mt-3 font-sans text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          Join a carpool
        </h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-muted-foreground">
          Enter the event code from your invitation, or open the link you were sent.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="session-code" className="sr-only">Session code</label>
          <input
            id="session-code"
            name="session"
            autoComplete="off"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder="e.g. ABC123"
            aria-describedby={error ? "session-error" : undefined}
            className="min-h-12 flex-1 rounded-xl border border-border bg-white/80 px-4 font-mono text-lg tracking-[0.14em] text-foreground shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-ring/25"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="min-h-12 rounded-xl bg-primary px-7 text-sm font-semibold text-primary-foreground shadow-sm transition hover:brightness-95 disabled:cursor-wait disabled:opacity-60"
          >
            {isLoading ? "Checking…" : "Find session"}
          </button>
        </form>

        {isLoading && (
          <p role="status" aria-live="polite" className="mt-5 text-sm text-muted-foreground">
            Looking up session {code}…
          </p>
        )}

        {error && (
          <div
            id="session-error"
            role="alert"
            className="mt-5 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          >
            <p>{error}</p>
            {(error === "Sign in to view this session." ||
              error === "Sign in with an account that can access this session.") && (
              <Link href="/login" className="mt-2 inline-block font-semibold underline underline-offset-4">
                Sign in with Google
              </Link>
            )}
          </div>
        )}

        {session && (
          <article className="mt-8 overflow-hidden rounded-2xl border border-border bg-white/85 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.35)]">
            <div className="border-b border-border bg-white/60 px-6 py-5 sm:px-8">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Session found</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{session.title}</h2>
              {session.description && <p className="mt-2 leading-6 text-muted-foreground">{session.description}</p>}
            </div>
            <dl className="grid gap-x-8 gap-y-5 px-6 py-6 sm:grid-cols-2 sm:px-8">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Departure window</dt>
                <dd className="mt-1 text-sm text-foreground">{displayDate(session.earliest_pickup)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Latest arrival</dt>
                <dd className="mt-1 text-sm text-foreground">{displayDate(session.latest_arrival)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Registration deadline</dt>
                <dd className="mt-1 text-sm text-foreground">{displayDate(session.registration_deadline)}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Trip direction</dt>
                <dd className="mt-1 text-sm text-foreground">{session.trip_mode === "to_destination" ? "To the destination" : "From the origin"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Status</dt>
                <dd className="mt-1 text-sm capitalize text-foreground">{session.status.replaceAll("_", " ")}</dd>
              </div>
            </dl>
            <div className="border-t border-border bg-muted/60 px-6 py-6 sm:px-8">
              <h3 className="font-semibold text-foreground">Ready to ride?</h3>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Choose how you would like to travel. Registration details will be collected in the next step.
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <button type="button" disabled className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-muted-foreground opacity-70">Register as Driver</button>
                <button type="button" disabled className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-muted-foreground opacity-70">Register as Passenger</button>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">Registration forms are coming in a later phase.</p>
            </div>
          </article>
        )}

        {!session && !isLoading && !error && (
          <p className="mt-6 text-sm text-muted-foreground">
            Need an account first? <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">Sign in with Google</Link>
          </p>
        )}
      </section>
    </main>
  );
}

function RegisterRoute() {
  const searchParams = useSearchParams();
  const linkedCode = (searchParams.get("session") ?? "").trim().toUpperCase();

  return <RegisterContent key={linkedCode || "manual-entry"} linkedCode={linkedCode} />;
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<main className="flex flex-1 items-center justify-center px-4"><p role="status" className="text-sm text-muted-foreground">Loading registration…</p></main>}>
      <RegisterRoute />
    </Suspense>
  );
}
