import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "@/hooks/useAuth";
import { userManager } from "@/lib/cognito";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

// ─── Types ────────────────────────────────────────────────────────────────────

type ErrorKind = "state-mismatch" | "network" | "generic";

interface CallbackError {
  kind: ErrorKind;
  message: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const MAX_RETRIES = 3;

function classifyError(error: unknown): CallbackError {
  const message =
    error instanceof Error ? error.message : String(error ?? "Unknown error");

  if (/state/i.test(message)) {
    return {
      kind: "state-mismatch",
      message:
        "Your login session expired or was used in another tab. Please try again.",
    };
  }

  if (
    /network|fetch|failed to fetch|econnrefused|timeout/i.test(message) ||
    (error instanceof TypeError && message.toLowerCase().includes("fetch"))
  ) {
    return {
      kind: "network",
      message:
        "Could not complete sign-in. Please check your connection and try again.",
    };
  }

  return {
    kind: "generic",
    message: "Sign-in failed. Please try again.",
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

/**
 * CallbackHandler — rendered at /callback route.
 * Processes the Cognito OIDC token exchange and redirects to /dashboard.
 */
export function CallbackHandler() {
  const navigate = useNavigate();
  const { loginWithGoogle } = useAuth();

  const [processing, setProcessing] = useState(true);
  const [callbackError, setCallbackError] = useState<CallbackError | null>(null);
  const retryCountRef = useRef(0);

  const runCallback = useCallback(async () => {
    setProcessing(true);
    setCallbackError(null);

    try {
      await userManager.signinRedirectCallback();
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const classified = classifyError(err);

      if (classified.kind === "state-mismatch") {
        await userManager.clearStaleState().catch(() => {});
      }

      setCallbackError(classified);
      setProcessing(false);
    }
  }, [navigate]);

  useEffect(() => {
    runCallback();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRetry = useCallback(async () => {
    if (retryCountRef.current >= MAX_RETRIES) return;
    retryCountRef.current += 1;
    await runCallback();
  }, [runCallback]);

  // Spinner while processing
  if (processing) {
    return (
      <div
        className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background"
        aria-live="polite"
        aria-label="Signing you in"
      >
        <svg
          className="mb-4 size-10 animate-spin text-primary"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <p className="text-sm text-muted-foreground">Signing you in…</p>
      </div>
    );
  }

  // Error state
  if (callbackError) {
    const isNetworkError = callbackError.kind === "network";
    const canRetry = isNetworkError && retryCountRef.current < MAX_RETRIES;

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
        <Card className="w-full max-w-sm mx-4">
          <CardHeader>
            <CardTitle>
              {callbackError.kind === "state-mismatch"
                ? "Session expired"
                : callbackError.kind === "network"
                  ? "Connection error"
                  : "Sign-in failed"}
            </CardTitle>
            <CardDescription>{callbackError.message}</CardDescription>
          </CardHeader>
          <CardContent>
            {isNetworkError && retryCountRef.current >= MAX_RETRIES && (
              <p className="text-xs text-muted-foreground">
                Maximum retry attempts reached. Please check your connection and
                try logging in again.
              </p>
            )}
          </CardContent>
          <CardFooter className="gap-2">
            {canRetry && (
              <Button variant="outline" onClick={handleRetry} className="flex-1">
                Retry
              </Button>
            )}
            <Button onClick={loginWithGoogle} className="flex-1">
              Log In Again
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return null;
}
