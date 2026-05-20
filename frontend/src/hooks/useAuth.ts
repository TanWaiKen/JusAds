import { useContext } from "react";
import { AuthContext } from "../lib/authProvider";
import type { AuthContextValue } from "../lib/authProvider";

/**
 * Custom hook to consume the AuthContext.
 *
 * Must be called inside a component that is a descendant of `AuthProvider`.
 * Throws if called outside of an `AuthProvider`.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (context === undefined || context === null) {
    throw new Error(
      "useAuth must be used within an AuthProvider. " +
      "Wrap your component tree with <AuthProvider> to use this hook."
    );
  }

  return context;
}
