"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { GoogleLogin, type CredentialResponse } from "@react-oauth/google";
import { useAuth } from "@/lib/auth-context";

const GOOGLE_CLIENT_ID =
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSuccess = useCallback(
    async (response: CredentialResponse) => {
      setError(null);
      const idToken = response.credential;
      if (!idToken) {
        setError("Google did not return an ID token. Please try again.");
        return;
      }
      setIsSubmitting(true);
      try {
        await login(idToken);
        router.push("/");
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Sign-in failed. Please try again.";
        setError(message);
      } finally {
        setIsSubmitting(false);
      }
    },
    [login, router],
  );

  const handleError = useCallback(() => {
    setError("Google sign-in was cancelled or failed. Please try again.");
  }, []);

  if (!GOOGLE_CLIENT_ID) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-4">
        <div
          role="alert"
          className="max-w-md rounded-md border border-destructive bg-destructive/10 p-4 text-sm text-destructive"
        >
          Google sign-in is not configured. Set{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">
            NEXT_PUBLIC_GOOGLE_CLIENT_ID
          </code>{" "}
          in <code className="rounded bg-muted px-1 py-0.5 text-xs">.env.local</code>{" "}
          to enable it.
        </div>
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4">
      <h1 className="text-3xl font-semibold tracking-tight text-foreground">
        Sign in
      </h1>
      <p className="mt-3 max-w-md text-center text-muted-foreground">
        Continue with Google to coordinate carpools for your event.
      </p>

      <div className="mt-6">
        <GoogleLogin
          onSuccess={handleSuccess}
          onError={handleError}
          useOneTap={false}
          auto_select={false}
        />
      </div>

      {isSubmitting && (
        <p
          className="mt-4 text-sm text-muted-foreground"
          aria-live="polite"
        >
          Signing you in…
        </p>
      )}

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mt-4 max-w-md rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}
    </main>
  );
}
