import { useRef, useEffect, useMemo } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Video, Image, Music, FileText, AlertTriangle } from "lucide-react";
import type { Project } from "@/types/compliance";
import { WORKFLOW_STEPS } from "@/types/compliance";

gsap.registerPlugin(useGSAP);

interface ProjectSidebarProps {
  projects: Project[];
  activeProjectId: string | null;
  onSelectProject: (projectId: string) => void;
}

/** Map media type to a Lucide icon component */
function MediaIcon({ type }: { type: Project["mediaType"] }) {
  const iconClass = "w-4 h-4 text-text-muted";
  switch (type) {
    case "video":
      return <Video className={iconClass} aria-hidden="true" />;
    case "image":
      return <Image className={iconClass} aria-hidden="true" />;
    case "audio":
      return <Music className={iconClass} aria-hidden="true" />;
    case "text":
      return <FileText className={iconClass} aria-hidden="true" />;
  }
}

/** Risk level dot color mapping */
function RiskDot({ riskLevel }: { riskLevel: "High" | "Medium" | "Low" | null }) {
  if (!riskLevel) return null;

  let colorClass: string;
  switch (riskLevel) {
    case "High":
      colorClass = "bg-red-500";
      break;
    case "Medium":
      colorClass = "bg-amber-500";
      break;
    case "Low":
      colorClass = "bg-emerald-500";
      break;
  }

  return (
    <span
      className={`w-2 h-2 rounded-full shrink-0 ${colorClass}`}
      aria-label={`${riskLevel} risk`}
    />
  );
}

/** Get the display label for the current step */
function getStepLabel(stepId: Project["currentStep"]): string {
  const step = WORKFLOW_STEPS.find((s) => s.id === stepId);
  return step?.label ?? stepId;
}

/** Derive risk level from the project result */
function getRiskLevel(project: Project): "High" | "Medium" | "Low" | null {
  return project.result?.risk_level ?? null;
}

export function ProjectSidebar({
  projects,
  activeProjectId,
  onSelectProject,
}: ProjectSidebarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const prevProjectCountRef = useRef(projects.length);

  // Sort projects by createdAt descending (newest first)
  const sortedProjects = useMemo(
    () => [...projects].sort((a, b) => b.createdAt - a.createdAt),
    [projects]
  );

  // GSAP animation for new project entrance (slide down + fade in)
  useEffect(() => {
    if (projects.length > prevProjectCountRef.current && listRef.current) {
      // A new project was added — animate the first child (newest, at the top)
      const firstItem = listRef.current.querySelector("[data-sidebar-item]:first-child");
      if (firstItem) {
        gsap.fromTo(
          firstItem,
          { y: -20, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.3, ease: "power2.out" }
        );
      }
    }
    prevProjectCountRef.current = projects.length;
  }, [projects.length]);

  // GSAP animation for selection change (background emphasis transition)
  useGSAP(
    () => {
      if (!listRef.current) return;
      const items = listRef.current.querySelectorAll("[data-sidebar-item]");
      items.forEach((item) => {
        const isActive = item.getAttribute("data-active") === "true";
        const highlight = item.querySelector("[data-highlight]");
        if (highlight) {
          gsap.to(highlight, {
            autoAlpha: isActive ? 1 : 0,
            duration: 0.2,
            ease: "power1.out",
          });
        }
      });
    },
    { scope: containerRef, dependencies: [activeProjectId] }
  );

  // Keyboard navigation: Arrow keys to move between items
  function handleKeyDown(e: React.KeyboardEvent, projectId: string, index: number) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectProject(projectId);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = index + 1;
      if (nextIndex < sortedProjects.length) {
        const nextItem = listRef.current?.querySelectorAll("[data-sidebar-item]")[nextIndex] as HTMLElement | undefined;
        nextItem?.focus();
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prevIndex = index - 1;
      if (prevIndex >= 0) {
        const prevItem = listRef.current?.querySelectorAll("[data-sidebar-item]")[prevIndex] as HTMLElement | undefined;
        prevItem?.focus();
      }
    }
  }

  return (
    <aside ref={containerRef} aria-label="Compliance projects" className="w-64 shrink-0">
      <div
        ref={listRef}
        role="listbox"
        aria-label="Project list"
        className="flex flex-col gap-1 p-2"
      >
        {sortedProjects.map((project, index) => {
          const isActive = project.id === activeProjectId;
          const riskLevel = getRiskLevel(project);

          return (
            <div
              key={project.id}
              role="option"
              aria-selected={isActive}
              tabIndex={0}
              data-sidebar-item
              data-active={isActive}
              className="relative rounded-lg px-3 py-2.5 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
              onClick={() => onSelectProject(project.id)}
              onKeyDown={(e) => handleKeyDown(e, project.id, index)}
            >
              {/* Background highlight layer for GSAP autoAlpha animation */}
              <div
                data-highlight
                className="absolute inset-0 rounded-lg bg-surface-inset pointer-events-none"
                style={{ visibility: isActive ? "visible" : "hidden", opacity: isActive ? 1 : 0 }}
              />

              {/* Content */}
              <div className="relative flex items-center gap-2.5">
                <MediaIcon type={project.mediaType} />

                <div className="flex-1 min-w-0">
                  <p className="font-label-ui text-label-ui text-text-primary truncate">
                    {project.campaignName}
                  </p>
                  <p className="text-code-xs font-code-xs text-text-muted">
                    {getStepLabel(project.currentStep)}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {project.error && (
                    <AlertTriangle
                      className="w-3.5 h-3.5 text-error"
                      aria-label="Error"
                    />
                  )}
                  <RiskDot riskLevel={riskLevel} />
                </div>
              </div>
            </div>
          );
        })}

        {/* Empty state */}
        {sortedProjects.length === 0 && (
          <div className="px-3 py-6 text-center">
            <p className="text-body-md font-body-md text-text-muted">
              No projects yet
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
