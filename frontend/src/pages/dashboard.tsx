import { NavLink, Outlet } from "react-router";
import {
  LayoutDashboard,
  Megaphone,
  TrendingUp,
  Image as ImageIcon,
  ShieldCheck,
  UserCircle,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";

// ─── Nav Items ────────────────────────────────────────────────────────────────

interface NavItem {
  label: string;
  icon: React.ElementType;
  to: string;
  badge?: string;
}

const navItems: NavItem[] = [
  { label: "Home",       icon: LayoutDashboard, to: "/dashboard" },
  { label: "Profile",    icon: UserCircle,      to: "/dashboard/profile" },
  { label: "Campaigns",  icon: Megaphone,       to: "/dashboard/campaigns" },
  { label: "Assets",     icon: ImageIcon,       to: "/dashboard/assets" },
  { label: "Compliance", icon: ShieldCheck,     to: "/dashboard/compliance" },
];

// ─── DashboardShell ───────────────────────────────────────────────────────────

export default function DashboardShell() {
  const { user, picture, logout } = useAuth();

  const name = user?.profile.name ?? "";
  const initials = name ? name.slice(0, 2).toUpperCase() : "?";

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground font-sans">
      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        className="flex h-full w-[240px] shrink-0 flex-col border-r border-gray-200 dark:border-white/10 bg-[#fafafa] dark:bg-[#111116]"
        aria-label="Sidebar navigation"
      >
        {/* Brand */}
        <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-200 dark:border-white/10">
          <img src="/logo-black.png" alt="JusAds Logo" className="h-6 w-auto block dark:hidden" />
          <img src="/logo-white.png" alt="JusAds Logo" className="h-6 w-auto hidden dark:block" />
          <span className="font-semibold text-[15px] tracking-tight text-[#171717] dark:text-white">
            JusAds
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-4 py-6" aria-label="Main navigation">
          <ul className="flex flex-col gap-1.5">
            {navItems.map(({ label, icon: Icon, to, badge }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === "/dashboard"}
                  className={({ isActive }) =>
                    [
                      "flex items-center gap-3 rounded-[6px] px-3 py-2 text-[14px] font-medium transition-all duration-200",
                      isActive
                        ? "bg-black/5 dark:bg-white/10 text-[#171717] dark:text-white"
                        : "text-gray-600 dark:text-gray-400 hover:text-[#171717] dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5",
                    ].join(" ")
                  }
                >
                  <Icon size={16} aria-hidden="true" strokeWidth={2.5} />
                  <span className="flex-1">{label}</span>
                  {badge && (
                    <span className="rounded-full bg-gray-200 dark:bg-white/10 px-2 py-[2px] text-[10px] uppercase font-bold tracking-wider text-gray-500 dark:text-gray-400">
                      {badge}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      {/* ── Main Area ───────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="sticky top-0 z-10 flex items-center justify-end gap-4 border-b border-gray-200 dark:border-white/10 bg-white/80 dark:bg-[#0a0a0f]/80 backdrop-blur-md px-8 py-4">
          {/* Avatar */}
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#171717] dark:bg-white text-white dark:text-[#171717] text-[12px] font-semibold select-none shadow-sm"
            aria-label={`User avatar: ${initials}`}
          >
            {picture ? (
              <img
                src={picture}
                alt="User avatar"
                className="h-full w-full object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              initials
            )}
          </div>

          {/* Log Out */}
          <button
            onClick={() => void logout()}
            className="rounded-[6px] border border-gray-200 dark:border-white/10 px-3 py-1.5 text-[13px] font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 hover:text-[#171717] dark:hover:text-white transition-all duration-200 cursor-pointer"
          >
            Log Out
          </button>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-hidden flex flex-col">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
