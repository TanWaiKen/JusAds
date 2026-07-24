import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Sun, Moon, Menu, X } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/components/theme-provider";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuthAction {
  isAuthenticated: boolean;
  onOpenLogin: () => void;
  status: "loading" | "authenticated" | "unauthenticated";
}

// ─── Navigation Items ─────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { href: "#sample-result", label: "Sample result" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
] as const;

// ─── Header Component ─────────────────────────────────────────────────────────

export default function Header({ onAuthAction }: { onAuthAction: AuthAction }) {
  const navigate = useNavigate();
  const { user, picture, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const { status, isAuthenticated } = onAuthAction;
  const name = user?.profile?.name ?? "";
  const initials = name ? name.slice(0, 2).toUpperCase() : "?";

  const handleAuthAction = () => {
    if (isAuthenticated) navigate("/dashboard");
    else onAuthAction.onOpenLogin();
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border-subtle bg-background/85 backdrop-blur-md">
      <nav className="relative mx-auto flex max-w-[1200px] items-center justify-between px-5 py-3 md:px-10 md:py-4">
        <Link to="/" className="flex items-center gap-2 group">
          <img src="/logo-black.png" alt="JusAds Logo" className="h-8 w-auto block dark:hidden group-hover:scale-105 transition-transform duration-200" />
          <img src="/logo-white.png" alt="JusAds Logo" className="h-8 w-auto hidden dark:block group-hover:scale-105 transition-transform duration-200" />
          <span className="font-semibold text-body-md tracking-tight text-text-heading">JusAds</span>
        </Link>

        <div className="hidden md:flex items-center gap-8">
          {NAV_ITEMS.map(({ href, label }) => (
            <a key={href} href={href} className="text-label-ui font-medium text-text-body hover:text-text-heading transition-colors duration-200">
              {label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <button
            onClick={toggleTheme}
            className="rounded-md p-2 shadow-[0_0_0_1px_rgba(0,0,0,0.08)] hover:bg-surface-inset transition-colors cursor-pointer"
            aria-label="Toggle dark mode"
          >
            <Sun size={16} className="hidden dark:block text-text-heading" />
            <Moon size={16} className="block dark:hidden text-text-heading" />
          </button>
          {status === "loading" && (
            <>
              <Skeleton className="h-[36px] w-[56px] rounded-[4px]" />
              <Skeleton className="h-[36px] w-[104px] rounded-[4px]" />
            </>
          )}
          {status === "unauthenticated" && (
            <>
              <button onClick={handleAuthAction} className="inline-flex items-center bg-white hover:bg-surface-inset active:scale-[0.98] text-text-heading px-4 py-2 rounded-md text-sm font-medium transition-premium brutalist-shadow-black dark:shadow-none cursor-pointer">
                Log In
              </button>
              <button onClick={handleAuthAction} className="inline-flex items-center bg-[#171717] hover:bg-[#333] active:scale-[0.98] text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 px-4 py-2 rounded-md text-sm font-medium transition-premium brutalist-shadow-subtle dark:shadow-none cursor-pointer">
                Create free ad
              </button>
            </>
          )}
          {status === "authenticated" && user && (
            <div className="flex items-center gap-3">
              <button onClick={() => navigate("/dashboard")} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <div className="h-8 w-8 rounded-full overflow-hidden ring-2 ring-border-default shrink-0">
                  {picture
                    ? <img src={picture} alt="Profile" className="h-full w-full object-cover" referrerPolicy="no-referrer" />
                    : <div className="h-full w-full flex items-center justify-center bg-foreground text-background text-[12px] font-semibold">{initials}</div>
                  }
                </div>
                <span className="text-label-ui font-medium text-text-heading hidden sm:block">{user.profile.name}</span>
              </button>
              <button onClick={() => void logout()} className="text-label-ui font-medium text-text-body hover:text-text-heading px-2 py-1 transition-all cursor-pointer">
                Log Out
              </button>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsMenuOpen((open) => !open)}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-border-default text-text-heading md:hidden"
          aria-label={isMenuOpen ? "Close menu" : "Open menu"}
          aria-expanded={isMenuOpen}
        >
          {isMenuOpen ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
        </button>

        {isMenuOpen && (
          <div className="absolute left-4 right-4 top-[calc(100%+8px)] rounded-xl border border-border-default bg-surface-card p-3 shadow-xl md:hidden">
            <div className="flex flex-col">
              {NAV_ITEMS.map(({ href, label }) => (
                <a key={href} href={href} onClick={() => setIsMenuOpen(false)} className="flex min-h-11 items-center rounded-lg px-3 text-base font-medium text-text-heading hover:bg-surface-inset">
                  {label}
                </a>
              ))}
              <div className="my-2 border-t border-border-subtle" />
              <button type="button" onClick={toggleTheme} className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-left text-base font-medium text-text-heading hover:bg-surface-inset">
                {theme === "dark" ? <Sun className="h-5 w-5" aria-hidden="true" /> : <Moon className="h-5 w-5" aria-hidden="true" />}
                {theme === "dark" ? "Use light mode" : "Use dark mode"}
              </button>
              <button type="button" onClick={handleAuthAction} className="mt-2 min-h-12 rounded-lg bg-[#171717] px-4 text-base font-semibold text-white dark:bg-white dark:text-black">
                {isAuthenticated ? "Open my workspace" : "Create my first free ad"}
              </button>
              {!isAuthenticated && (
                <button type="button" onClick={handleAuthAction} className="min-h-11 text-sm font-semibold text-text-body">
                  Already have an account? Log in
                </button>
              )}
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
