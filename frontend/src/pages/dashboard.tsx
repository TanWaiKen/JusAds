import { useRef, useState, useEffect } from "react";
import { Outlet, useNavigate, useLocation, useParams } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Menu, Loader2 } from "lucide-react";
import { Sidebar, SIDEBAR_WIDTH } from "@/components/layout/Sidebar";
import type { SidebarHandle } from "@/components/layout/Sidebar";
import { useAuth } from "@/hooks/useAuth";
import "./dashboard.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

gsap.registerPlugin(useGSAP);

// ─── DashboardShell ───────────────────────────────────────────────────────────

export default function DashboardShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 1024);
  const sidebarHandleRef = useRef<SidebarHandle>(null);
  const headerRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);

  const { user, status } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = useParams<{ projectId?: string }>();
  const [checkingOnboarding, setCheckingOnboarding] = useState(true);

  // Collapse sidebar when a project is selected
  useEffect(() => {
    if (projectId) {
      setSidebarOpen(false);
    } else {
      setSidebarOpen(true);
    }
  }, [projectId]);

  // Track desktop vs mobile
  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Onboarding gate check
  useEffect(() => {
    if (status === "loading") return;
    if (status === "unauthenticated") {
      setCheckingOnboarding(false);
      return;
    }

    const email = user?.profile?.email;
    if (!email) {
      setCheckingOnboarding(false);
      return;
    }

    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/profile/${email}/onboarding-status`);
        if (res.ok) {
          const data = await res.json();
          const isOnboardingPath = location.pathname === "/dashboard/onboarding";
          
          if (!data.onboarding_complete) {
            // First-time user: force them to onboard
            if (!isOnboardingPath) {
              navigate("/dashboard/onboarding", { replace: true });
            }
          }
          // If already onboarded and on onboarding page — let them stay (they're editing).
          // Only first-time users get forced to onboard; returning users can access it freely.
        }
      } catch (err) {
        console.error("Failed to check onboarding status:", err);
      } finally {
        setCheckingOnboarding(false);
      }
    };

    checkStatus();
  }, [user, status, location.pathname, navigate]);

  // Animate header entrance on mount
  useGSAP(
    () => {
      if (!headerRef.current) return;
      gsap.fromTo(".header-left", {
        y: -8,
        autoAlpha: 0,
      }, {
        y: 0,
        autoAlpha: 1,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: headerRef, dependencies: [checkingOnboarding, status] }
  );

  if (status === "loading" || checkingOnboarding) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-muted-foreground animate-pulse">
            Verifying profile setup status...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-shell relative flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Backdrop — only on mobile when sidebar is open */}
      {!isDesktop && (
        <div
          className="sidebar-backdrop fixed inset-0 z-30 bg-black/40 backdrop-blur-xs opacity-0 pointer-events-none"
          onClick={() => sidebarHandleRef.current?.close()}
          style={{ visibility: "hidden" }}
        />
      )}

      {/* ── Sidebar Component ──────────────────────────────────────────── */}
      <Sidebar
        ref={sidebarHandleRef}
        isOpen={sidebarOpen}
        isDesktop={isDesktop}
        onClose={() => setSidebarOpen(false)}
        onOpen={() => setSidebarOpen(true)}
      />

      {/* ── Main Column (header + content) ─────────────────────────────── */}
      <div
        className="flex flex-1 flex-col h-full w-full transition-all duration-300"
        style={{ paddingLeft: isDesktop && sidebarOpen ? SIDEBAR_WIDTH : 0 }}
      >
        {/* Header */}
        <header
          ref={headerRef}
          className="dashboard-header sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between bg-surface-card/80 backdrop-blur-md px-6 transition-all duration-300"
        >
          <div className="header-left flex items-center gap-3">
            {/* Hamburger — always shows when sidebar is closed */}
            {!sidebarOpen && (
              <button
                onClick={() => sidebarHandleRef.current?.open()}
                className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-surface-inset transition-colors"
                aria-label="Open navigation menu"
              >
                <Menu size={20} className="text-text-body" />
              </button>
            )}

            {/* Brand in header when sidebar is closed */}
            {!sidebarOpen && (
              <div className="flex items-center gap-2">
                <img src="/logo-black.png" alt="JusAds" className="h-5 w-auto block dark:hidden" />
                <img src="/logo-white.png" alt="JusAds" className="h-5 w-auto hidden dark:block" />
                <span className="font-bold text-[15px] tracking-tight text-text-primary dark:text-white">
                  JusAds
                </span>
              </div>
            )}

            {/* Desktop label when sidebar is open */}
            {sidebarOpen && (
              <span className="font-bold tracking-widest text-code-xs text-text-caption uppercase">
                Workspace Management
              </span>
            )}
          </div>

          <div className="header-right flex items-center gap-3" />
        </header>

        {/* Page Content */}
        <main ref={mainRef} className="dashboard-main grow overflow-y-auto overflow-x-hidden">
          <div className="dashboard-content">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
