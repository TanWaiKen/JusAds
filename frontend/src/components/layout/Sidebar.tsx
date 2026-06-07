import { useRef, forwardRef, useImperativeHandle, useCallback } from "react";
import { NavLink, useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  LayoutDashboard,
  Megaphone,
  Image as ImageIcon,
  ShieldCheck,
  TrendingUp,
  PanelLeftClose,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

gsap.registerPlugin(useGSAP);

// ─── Types ────────────────────────────────────────────────────────────────────

interface NavItem {
  label: string;
  icon: React.ElementType;
  to: string;
  badge?: string;
}

export interface SidebarHandle {
  open: () => void;
  close: () => void;
}

interface SidebarProps {
  isOpen: boolean;
  isDesktop: boolean;
  onClose: () => void;
  onOpen: () => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const navItems: NavItem[] = [
  { label: "Home", icon: LayoutDashboard, to: "/dashboard" },
  { label: "Campaigns", icon: Megaphone, to: "/dashboard/campaigns" },
  { label: "Assets", icon: ImageIcon, to: "/dashboard/assets" },
  { label: "Trends", icon: TrendingUp, to: "/dashboard/trends" },
  { label: "Compliance", icon: ShieldCheck, to: "/dashboard/compliance" },
];

export const SIDEBAR_WIDTH = 240;

// ─── Sidebar Component ────────────────────────────────────────────────────────

export const Sidebar = forwardRef<SidebarHandle, SidebarProps>(
  function Sidebar({ isOpen, isDesktop, onClose, onOpen }, ref) {
    const { user, picture } = useAuth();
    const navigate = useNavigate();
    const sidebarRef = useRef<HTMLElement>(null);

    const name = user?.profile.name ?? "";
    const initials = name ? name.slice(0, 2).toUpperCase() : "?";

    // Desktop: just toggle state, CSS transition handles the slide
    // Mobile: use GSAP for backdrop + slide animation
    const handleOpen = useCallback(() => {
      if (isDesktop) {
        onOpen();
      } else {
        onOpen();
        const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
        tl.to(sidebarRef.current, { x: 0, duration: 0.35 });
        tl.to(".sidebar-backdrop", { autoAlpha: 1, duration: 0.3 }, "<");
        tl.fromTo(".nav-item",
          { x: -12, opacity: 0 },
          {
            x: 0,
            opacity: 1,
            stagger: 0.03,
            duration: 0.25,
            ease: "power2.out",
            clearProps: "all",
          },
          "-=0.15"
        );
      }
    }, [isDesktop, onOpen]);

    const handleClose = useCallback(() => {
      if (isDesktop) {
        onClose();
      } else {
        const tl = gsap.timeline({
          defaults: { ease: "power2.inOut" },
          onComplete: onClose,
        });
        tl.to(sidebarRef.current, { x: -SIDEBAR_WIDTH, duration: 0.3 });
        tl.to(".sidebar-backdrop", { autoAlpha: 0, duration: 0.25 }, "<");
      }
    }, [isDesktop, onClose]);

    // Expose open/close to parent
    useImperativeHandle(ref, () => ({
      open: handleOpen,
      close: handleClose,
    }));

    // Animate nav items on initial mount when sidebar starts open
    useGSAP(() => {
      if (!isOpen) return;
      gsap.fromTo(".nav-item",
        { x: -10, opacity: 0 },
        {
          x: 0,
          opacity: 1,
          stagger: 0.04,
          duration: 0.35,
          ease: "power2.out",
          clearProps: "all",
        }
      );
    }, { scope: sidebarRef, dependencies: [] });

    return (
      <aside
        ref={sidebarRef}
        className="fixed top-0 left-0 z-40 flex h-full flex-col bg-surface-card border-r border-border-default shadow-xl lg:shadow-none transition-transform duration-300"
        style={{
          width: SIDEBAR_WIDTH,
          transform: isOpen ? "translateX(0px)" : `translateX(-${SIDEBAR_WIDTH}px)`,
        }}
        aria-label="Sidebar navigation"
      >
        {/* Sidebar Header with close button */}
        <div className="flex items-center justify-between px-4 h-16 shrink-0 border-b border-border-default">
          <div className="flex items-center gap-2">
            <img src="/logo-black.png" alt="JusAds" className="h-6 w-auto block dark:hidden" />
            <img src="/logo-white.png" alt="JusAds" className="h-6 w-auto hidden dark:block" />
            <span className="font-bold text-body-md tracking-tight text-text-primary dark:text-white">
              JusAds
            </span>
          </div>
          <button
            onClick={handleClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-surface-inset transition-colors"
            aria-label="Close sidebar"
          >
            <PanelLeftClose size={18} className="text-text-body" />
          </button>
        </div>

        {/* Nav Links — clicking a link does NOT close the sidebar on desktop */}
        <nav className="flex-1 overflow-y-auto px-3 py-5" aria-label="Main navigation">
          <ul className="flex flex-col gap-1">
            {navItems.map(({ label, icon: Icon, to, badge }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === "/dashboard"}
                  onClick={() => { if (!isDesktop) handleClose(); }}
                  className={({ isActive }) =>
                    [
                      "nav-item flex items-center gap-3 rounded-xl px-3.5 py-3 text-label-ui font-semibold transition-all duration-200",
                      isActive
                        ? "bg-accent-blue/10 text-accent-blue shadow-xs"
                        : "text-text-body hover:text-text-heading hover:bg-surface-inset",
                    ].join(" ")
                  }
                >
                  <Icon size={18} aria-hidden="true" strokeWidth={2.2} />
                  <span className="grow">{label}</span>
                  {badge && (
                    <span className="rounded-full bg-surface-inset px-2 py-[2px] text-[10px] uppercase font-bold tracking-wider text-text-caption">
                      {badge}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* User Profile — navigates to profile page */}
        <div className="px-3 py-4 border-t border-border-default">
          <button
            onClick={() => { if (!isDesktop) handleClose(); navigate("/dashboard/profile"); }}
            className="flex items-center gap-3 w-full rounded-xl px-2 py-2 hover:bg-surface-inset transition-colors cursor-pointer text-left"
            title="Go to profile"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-text-primary dark:bg-white text-white dark:text-text-primary text-[12px] font-bold select-none ring-2 ring-border-subtle shadow-xs">
              {picture ? (
                <img src={picture} alt="Avatar" className="h-full w-full object-cover" referrerPolicy="no-referrer" />
              ) : (
                initials
              )}
            </div>
            <div className="grow min-w-0">
              <p className="text-code-sm font-bold text-text-heading truncate">
                {name || "User"}
              </p>
              <p className="text-code-xs text-text-caption truncate">
                {user?.profile.email ?? ""}
              </p>
            </div>
          </button>
        </div>
      </aside>
    );
  }
);
