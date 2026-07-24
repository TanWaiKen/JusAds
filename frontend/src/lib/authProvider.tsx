import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { User } from "oidc-client-ts";
import { toast } from "sonner";
import { userManager, signOutRedirect } from "./cognito";

// ─── Types ────────────────────────────────────────────────────────────────────

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  picture: string | null;
  loginWithGoogle: () => Promise<void>;
  loginWithEmail: (email: string) => Promise<void>;
  logout: () => Promise<void>;
  handleCallback: () => Promise<User>;
}

// ─── Context ──────────────────────────────────────────────────────────────────

export const AuthContext = createContext<AuthContextValue | null>(null);

const DEVELOPMENT_BYPASS_EMAIL = "developer@jusads.com";
const DEVELOPMENT_SESSION_KEY = "jusads-development-user";

function createDevelopmentUser(email: string): User {
  return {
    profile: {
      sub: "local-development-user",
      email,
      email_verified: true,
      name: "JusAds Developer",
    },
    expired: false,
  } as User;
}

function getDevelopmentSessionUser(): User | null {
  if (!import.meta.env.DEV) return null;
  try {
    const email = window.sessionStorage.getItem(DEVELOPMENT_SESSION_KEY);
    return email === DEVELOPMENT_BYPASS_EMAIL ? createDevelopmentUser(email) : null;
  } catch {
    return null;
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// Cognito maps Google's `picture` claim to the `profile` field in the ID token.
// Read it directly — no network call needed.
function getPicture(user: User | null): string | null {
  const p = user?.profile?.profile;
  return typeof p === "string" && p.startsWith("http") ? p : null;
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // Rehydrate the real OIDC session and subscribe to UserManager events.
  useEffect(() => {
    const developmentUser = getDevelopmentSessionUser();
    if (developmentUser) {
      setUser(developmentUser);
      setStatus("authenticated");
      return;
    }

    userManager.getUser().then((existingUser) => {
      if (existingUser && !existingUser.expired) {
        setUser(existingUser);
        setStatus("authenticated");
      } else {
        setUser(null);
        setStatus("unauthenticated");
      }
    }).catch(() => {
      setUser(null);
      setStatus("unauthenticated");
    });

    const onUserLoaded = (loadedUser: User) => {
      setUser(loadedUser);
      setStatus("authenticated");
    };

    const onUserUnloaded = () => {
      setUser(null);
      setStatus("unauthenticated");
    };

    const onSilentRenewError = () => {
      setUser(null);
      setStatus("unauthenticated");
      toast.error("Your session has expired. Please log in again.");
    };

    const onAccessTokenExpiring = () => {
      userManager.signinSilent().catch(() => {});
    };

    userManager.events.addUserLoaded(onUserLoaded);
    userManager.events.addUserUnloaded(onUserUnloaded);
    userManager.events.addSilentRenewError(onSilentRenewError);
    userManager.events.addAccessTokenExpiring(onAccessTokenExpiring);

    return () => {
      userManager.events.removeUserLoaded(onUserLoaded);
      userManager.events.removeUserUnloaded(onUserUnloaded);
      userManager.events.removeSilentRenewError(onSilentRenewError);
      userManager.events.removeAccessTokenExpiring(onAccessTokenExpiring);
    };
  }, []);

  const loginWithGoogle = useCallback(async () => {
    try {
      await userManager.signinRedirect({
        extraQueryParams: {
          identity_provider: "Google",
          prompt: "select_account",
        },
      });
    } catch {
      toast.error("Could not reach login service. Please try again.");
    }
  }, []);

  const loginWithEmail = useCallback(async (email: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    if (import.meta.env.DEV && normalizedEmail === DEVELOPMENT_BYPASS_EMAIL) {
      window.sessionStorage.setItem(DEVELOPMENT_SESSION_KEY, normalizedEmail);
      setUser(createDevelopmentUser(normalizedEmail));
      setStatus("authenticated");
      return;
    }
    await userManager.signinRedirect({
      extraQueryParams: { login_hint: normalizedEmail },
    });
  }, []);

  const logout = useCallback(async () => {
    setIsLoggingOut(true);
    await new Promise(resolve => setTimeout(resolve, 600));
    if (import.meta.env.DEV) {
      window.sessionStorage.removeItem(DEVELOPMENT_SESSION_KEY);
    }
    setUser(null);
    setStatus("unauthenticated");
    await userManager.removeUser();
    await signOutRedirect();
  }, []);

  const handleCallback = useCallback(async () => {
    return userManager.signinRedirectCallback();
  }, []);

  const contextValue = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isAuthenticated: status === "authenticated",
      picture: getPicture(user),
      loginWithGoogle,
      loginWithEmail,
      logout,
      handleCallback,
    }),
    [user, status, loginWithGoogle, loginWithEmail, logout, handleCallback]
  );

  return (
    <AuthContext.Provider value={contextValue}>
      {children}

      {isLoggingOut && (
        <div className="fixed inset-0 z-9999 flex flex-col items-center justify-center bg-white/90 dark:bg-[#0a0a0f]/90 backdrop-blur-xl animate-in fade-in duration-500">
          <div className="relative flex items-center justify-center w-24 h-24 mb-4">
            <div className="absolute inset-0 rounded-full border-t-2 border-r-2 border-[#7B2FBE] animate-[spin_1.5s_linear_infinite]"></div>
            <div className="absolute inset-2 rounded-full border-b-2 border-l-2 border-[#FF6B9D] animate-[spin_2s_linear_infinite_reverse]"></div>
            <div className="absolute inset-4 rounded-full border-t-2 border-l-2 border-[#00D4AA] animate-spin"></div>
            <img src="/logo-black.png" className="w-6 h-6 absolute block dark:hidden animate-pulse" alt="Logo" />
            <img src="/logo-white.png" className="w-6 h-6 absolute hidden dark:block animate-pulse" alt="Logo" />
          </div>
          <h2 className="text-[20px] font-bold text-[#171717] dark:text-white tracking-[-0.02em] animate-pulse">
            Signing out securely...
          </h2>
          <p className="mt-2 text-[14px] text-gray-500 dark:text-gray-400 font-medium">
            See you next time!
          </p>
        </div>
      )}
    </AuthContext.Provider>
  );
}
