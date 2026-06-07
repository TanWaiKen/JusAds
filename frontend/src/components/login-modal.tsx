import { useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const { loginWithGoogle, loginWithEmail } = useAuth();
  const [loginError, setLoginError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleGoogleLogin = async () => {
    setLoginError(null);
    try {
      await loginWithGoogle();
    } catch {
      setLoginError(
        "Login service is unavailable. Please check your connection and try again."
      );
    }
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsLoading(true);
    try {
      await loginWithEmail(email);
      onClose();
    } catch {
      setLoginError("Failed to bypass login. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div
        className="bg-white dark:bg-surface-card w-full max-w-md rounded-[16px] shadow-2xl overflow-hidden relative border border-transparent dark:border-border-default"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-surface-inset rounded-full transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-8 flex flex-col items-center text-center">
          {/* Logo */}
          <div className="mb-6 flex justify-center">
            <img src="/logo-black.png" alt="JusAds Logo" className="h-10 w-auto block dark:hidden" />
            <img src="/logo-white.png" alt="JusAds Logo" className="h-10 w-auto hidden dark:block" />
          </div>

          <h2 className="text-[24px] font-bold text-gray-900 dark:text-text-heading mb-2">
            Welcome to JusAds
          </h2>
          <p className="text-[15px] text-gray-600 dark:text-text-body mb-6">
            Sign in to start localizing your ad campaigns instantly.
          </p>

          {/* Google Sign In Button */}
          <button
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center gap-3 bg-white dark:bg-surface-elevated border border-gray-200 dark:border-border-default text-gray-900 dark:text-text-heading font-semibold py-3 px-4 rounded-[8px] hover:bg-gray-50 dark:hover:bg-surface-inset hover:shadow-sm transition-all active:scale-[0.98] cursor-pointer"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            Continue with Google
          </button>

          {/* Dev Bypass Section */}
          <div className="relative flex py-5 items-center w-full">
            <div className="grow border-t border-gray-100 dark:border-white/5"></div>
            <span className="shrink mx-4 text-gray-400 dark:text-gray-500 text-[10px] font-bold uppercase tracking-widest">
              Or Local Bypass
            </span>
            <div className="grow border-t border-gray-100 dark:border-white/5"></div>
          </div>

          <form onSubmit={handleEmailLogin} className="w-full space-y-3">
            <input
              type="email"
              required
              placeholder="developer@jusads.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full text-sm bg-transparent border border-gray-200 dark:border-border-default rounded-[8px] px-3.5 py-2.5 outline-hidden text-gray-900 dark:text-text-heading placeholder:text-gray-400 dark:placeholder:text-text-caption focus:border-[#0080FF] transition-all"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#171717] dark:bg-white text-white dark:text-[#171717] font-semibold py-2.5 px-4 rounded-[8px] text-sm hover:opacity-90 active:scale-[0.98] transition-all cursor-pointer"
            >
              {isLoading ? "Signing in..." : "Bypass with Email"}
            </button>
          </form>

          {/* Inline error message */}
          {loginError && (
            <p className="mt-3 text-[13px] text-red-600 dark:text-red-400 text-center">
              {loginError}
            </p>
          )}

          <p className="mt-6 text-[12px] text-gray-500 dark:text-text-caption">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>

      {/* Click outside to close (backdrop) */}
      <div className="absolute inset-0 z-[-1]" onClick={onClose}></div>
    </div>
  );
}
