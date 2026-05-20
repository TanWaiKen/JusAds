import { Navigate } from "react-router";
import { useAuth } from "@/hooks/useAuth";
import { Skeleton } from "@/components/ui/skeleton";

interface ProtectedRouteProps {
  redirectTo?: string;
  children: React.ReactNode;
}

/**
 * Guards routes that require authentication.
 *
 * - While auth status is resolving (`"loading"`): renders a full-viewport skeleton.
 * - When unauthenticated: redirects to `redirectTo` (defaults to `"/"`).
 * - When authenticated: renders `children`.
 *
 * Requirements: 4.1–4.5
 */
export function ProtectedRoute({ redirectTo, children }: ProtectedRouteProps) {
  const { status } = useAuth();

  // Requirement 4.1: show loading skeleton while status is resolving
  if (status === "loading") {
    return <Skeleton className="w-screen h-screen" />;
  }

  // Requirement 4.2 & 4.3: redirect unauthenticated users; default to "/"
  if (status === "unauthenticated") {
    const destination = redirectTo && redirectTo.length > 0 ? redirectTo : "/";
    return <Navigate to={destination} replace />;
  }

  // Requirement 4.4: render children when authenticated
  return <>{children}</>;
}
