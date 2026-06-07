import { useRef, useState, useEffect } from "react";
import { Outlet } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Menu } from "lucide-react";
import { Sidebar, SIDEBAR_WIDTH } from "@/components/layout/Sidebar";
import type { SidebarHandle } from "@/components/layout/Sidebar";

gsap.registerPlugin(useGSAP);

// ─── DashboardShell ───────────────────────────────────────────────────────────

export default function DashboardShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 1024);
  const sidebarHandleRef = useRef<SidebarHandle>(null);
  const headerRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);

  // Track desktop vs mobile
  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Animate header entrance on mount
  useGSAP(
    () => {
      gsap.from(".header-left", {
        y: -8,
        autoAlpha: 0,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: headerRef }
  );

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-background text-foreground font-sans">
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
          className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between border-b border-border-default bg-surface-card/80 backdrop-blur-md px-6 transition-all duration-300"
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
        <main ref={mainRef} className="grow overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
