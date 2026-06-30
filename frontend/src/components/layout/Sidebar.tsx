import { useRef, forwardRef, useImperativeHandle, useCallback, useState, useEffect } from "react";
import { NavLink, useNavigate, useParams } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  Image as ImageIcon,
  TrendingUp,
  PanelLeftClose,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { API_BASE } from "@/services/complianceApi";
import { deleteProject } from "@/services/taskApi";
import { toast } from "sonner";

gsap.registerPlugin(useGSAP);

// ─── Types ────────────────────────────────────────────────────────────────────

interface NavItem {
  label: string;
  icon: React.ElementType;
  to: string;
  badge?: string;
}

/** Shape returned by GET /api/projects */
interface SidebarProject {
  id: string;
  name: string;
  owner_email: string;
  created_at: string;
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
  { label: "Assets", icon: ImageIcon, to: "/dashboard/assets" },
  { label: "Trends", icon: TrendingUp, to: "/dashboard/trends" },
];

const MAX_VISIBLE_PROJECTS = 5;

export const SIDEBAR_WIDTH = 240;

// ─── Sidebar Component ────────────────────────────────────────────────────────

export const Sidebar = forwardRef<SidebarHandle, SidebarProps>(
  function Sidebar({ isOpen, isDesktop, onClose, onOpen }, ref) {
    const { user, picture } = useAuth();
    const navigate = useNavigate();
    const { projectId: activeProjectId } = useParams<{ projectId?: string }>();
    const sidebarRef = useRef<HTMLElement>(null);

    const name = user?.profile.name ?? "";
    const email = user?.profile.email ?? "";
    const initials = name ? name.slice(0, 2).toUpperCase() : "?";

    // ─── Projects State ─────────────────────────────────────────────────────
    const [projects, setProjects] = useState<SidebarProject[]>([]);
    const [projectsLoading, setProjectsLoading] = useState(false);
    const [showAllProjects, setShowAllProjects] = useState(false);

    // ─── New Project Modal State ────────────────────────────────────────────
    // (removed — now just navigates to /dashboard/new)

    // Fetch projects when user is authenticated
    useEffect(() => {
      if (!email) return;

      const controller = new AbortController();
      setProjectsLoading(true);

      fetch(`${API_BASE}/api/projects?username=${encodeURIComponent(email)}`, {
        signal: controller.signal,
      })
        .then((res) => {
          console.log(`[Sidebar] GET /api/projects?username=${email} → ${res.status}`);
          if (!res.ok) throw new Error(`Failed to fetch projects (${res.status})`);
          return res.json();
        })
        .then((data: SidebarProject[]) => {
          console.log(`[Sidebar] Loaded ${data.length} projects`, data);
          setProjects(data);
        })
        .catch((err) => {
          if (err.name !== "AbortError") {
            console.error("[Sidebar] Could not load projects:", err.message);
          }
        })
        .finally(() => {
          setProjectsLoading(false);
        });

      return () => controller.abort();
    }, [email]);

    // Re-fetch projects when a new project is created elsewhere (e.g. new-project.tsx)
    useEffect(() => {
      const handler = () => {
        if (!email) return;
        setProjectsLoading(true);
        fetch(`${API_BASE}/api/projects?username=${encodeURIComponent(email)}`)
          .then((res) => (res.ok ? res.json() : []))
          .then((data: SidebarProject[]) => setProjects(data))
          .catch(() => {/* non-fatal */})
          .finally(() => setProjectsLoading(false));
      };
      window.addEventListener("jusads:project-created", handler);
      return () => window.removeEventListener("jusads:project-created", handler);
    }, [email]);

    const visibleProjects = showAllProjects
      ? projects
      : projects.slice(0, MAX_VISIBLE_PROJECTS);

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
      <>
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

        {/* Nav Links */}
        <nav className="px-3 py-5" aria-label="Main navigation">
          <ul className="flex flex-col gap-1">
            {navItems.map(({ label, icon: Icon, to, badge }) => (
              <li key={to}>
                <NavLink
                  to={to}
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

        {/* ── Projects Section ──────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto px-3 border-t border-border-default">
          <div className="flex items-center justify-between px-2 pt-4 pb-2">
            <p className="font-bold text-body-md tracking-tight text-text-primary dark:text-white">
              Projects
            </p>
            <button
              type="button"
              onClick={() => {
                navigate("/dashboard/new");
                if (!isDesktop) handleClose();
              }}
              className="flex items-center justify-center h-6 w-6 rounded-md hover:bg-surface-inset transition-colors text-text-caption hover:text-accent-blue"
              title="New project"
              aria-label="Create new project"
            >
              <span className="text-[18px] leading-none font-light">+</span>
            </button>
          </div>

          {projectsLoading && (
            <div className="space-y-2 px-2">
              <div className="h-8 w-full rounded-lg bg-surface-inset animate-pulse" />
              <div className="h-8 w-full rounded-lg bg-surface-inset animate-pulse" />
              <div className="h-8 w-3/4 rounded-lg bg-surface-inset animate-pulse" />
            </div>
          )}

          {!projectsLoading && projects.length === 0 && (
            <p className="px-2 py-2 text-code-xs text-text-caption">
              No projects yet
            </p>
          )}

          {!projectsLoading && projects.length > 0 && (
            <ul className="flex flex-col gap-0.5">
              {visibleProjects.map((project) => {
                const isActive = project.id === activeProjectId;
                const TypeIcon = ShieldCheck;
                return (
                  <li key={project.id}>
                    <div
                      className={[
                        "flex items-center gap-2.5 w-full rounded-lg px-2.5 py-2 text-left transition-colors group",
                        isActive
                          ? "bg-accent-blue/10 text-accent-blue"
                          : "hover:bg-surface-inset",
                      ].join(" ")}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          navigate(`/dashboard/project/${project.id}`);
                          if (!isDesktop) handleClose();
                        }}
                        className="flex items-center gap-2.5 flex-1 min-w-0"
                        title={project.name}
                      >
                        <TypeIcon size={15} className={`shrink-0 ${isActive ? "text-accent-blue" : "text-text-caption group-hover:text-text-body"}`} />
                        <span className={`text-code-sm truncate ${isActive ? "text-accent-blue font-semibold" : "text-text-body group-hover:text-text-heading"}`}>
                          {project.name}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={async (e) => {
                          e.stopPropagation();
                          if (!confirm("Delete this project and all its data?")) return;
                          try {
                            await deleteProject(project.id);
                            setProjects((prev) => prev.filter((p) => p.id !== project.id));
                            if (isActive) navigate("/dashboard");
                            toast.success("Project deleted");
                          } catch {
                            toast.error("Failed to delete project");
                          }
                        }}
                        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-500/10"
                        title="Delete project"
                        aria-label="Delete project"
                      >
                        <Trash2 size={12} className="text-text-caption hover:text-red-500" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {!projectsLoading && projects.length > MAX_VISIBLE_PROJECTS && (
            <button
              type="button"
              onClick={() => setShowAllProjects((prev) => !prev)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 mt-1 text-code-xs text-text-caption hover:text-accent-blue transition-colors"
            >
              {showAllProjects ? (
                <>
                  <ChevronUp size={12} />
                  <span>Show less</span>
                </>
              ) : (
                <>
                  <ChevronDown size={12} />
                  <span>Show more</span>
                </>
              )}
            </button>
          )}
        </div>

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
                {email}
              </p>
            </div>
          </button>
        </div>
      </aside>
      </>
    );
  }
);
