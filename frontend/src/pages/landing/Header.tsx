import { Link, useNavigate } from "react-router";
import { Sun, Moon } from "lucide-react";
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
  { href: "#about", label: "About Us" },
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
    <header className="absolute top-0 left-0 right-0 z-50 w-full">
      <nav className="flex items-center justify-between w-full px-6 md:px-12 py-6">
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

        <div className="flex items-center gap-3">
          <button
            onClick={toggleTheme}
            className="p-2 rounded-full border border-border-default hover:bg-surface-inset transition-colors cursor-pointer"
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
              <button onClick={handleAuthAction} className="inline-flex items-center bg-white hover:bg-[#f6f6f5] active:scale-[0.98] text-black border-[1.5px] border-black dark:border-white dark:bg-white/10 dark:text-white dark:hover:bg-white/15 px-4 md:px-5 py-2.5 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-black dark:shadow-none cursor-pointer">
                Log In
              </button>
              <button onClick={handleAuthAction} className="inline-flex items-center bg-black hover:bg-neutral-900 active:scale-[0.98] text-white border-[1.5px] border-black dark:bg-white dark:text-black dark:border-white dark:hover:bg-gray-100 px-4 md:px-5 py-2.5 rounded-[6px] text-xs font-bold uppercase tracking-wider transition-premium brutalist-shadow-subtle dark:shadow-none cursor-pointer">
                Try for free
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
      </nav>
    </header>
  );
}
