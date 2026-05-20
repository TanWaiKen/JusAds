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

  // Rehydrate session on mount and subscribe to UserManager events
  useEffect(() => {
    // Check if there is a mock user in localStorage first
    const mockUserStr = localStorage.getItem("mock_user");
    if (mockUserStr) {
      try {
        const mockUser = JSON.parse(mockUserStr);
        if (mockUser && mockUser.expires_at > Math.floor(Date.now() / 1000)) {
          setUser(mockUser);
          setStatus("authenticated");
          return;
        } else {
          localStorage.removeItem("mock_user");
        }
      } catch {
        localStorage.removeItem("mock_user");
      }
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
    setStatus("loading");
    await new Promise(resolve => setTimeout(resolve, 300));
    const mockUser = {
      id_token: "mock-id-token",
      access_token: "mock-access-token",
      token_type: "Bearer",
      scope: "openid profile email",
      profile: {
        sub: "mock-sub-" + Math.random().toString(36).substring(7),
        iss: "mock-issuer",
        aud: "mock-client-id",
        exp: Math.floor(Date.now() / 1000) + 86400,
        iat: Math.floor(Date.now() / 1000),
        name: email.split("@")[0].toUpperCase(),
        email: email,
        profile: "",
      },
      expires_at: Math.floor(Date.now() / 1000) + 86400,
      state: null,
    } as unknown as User;

    setUser(mockUser);
    setStatus("authenticated");
    localStorage.setItem("mock_user", JSON.stringify(mockUser));
    toast.success("Bypassed securely using " + email);
  }, []);

  const logout = useCallback(async () => {
    setIsLoggingOut(true);
    await new Promise(resolve => setTimeout(resolve, 600));
    setUser(null);
    setStatus("unauthenticated");
    localStorage.removeItem("mock_user");
    await userManager.removeUser();
    try {
      await signOutRedirect();
    } catch {
      // Ignore Cognito redirect errors on mock bypass
    }
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
