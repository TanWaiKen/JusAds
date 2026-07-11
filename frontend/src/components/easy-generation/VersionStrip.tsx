import { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ChevronDown, ChevronUp, Image, Type } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";
import type { Version } from "@/types/easyGeneration";

gsap.registerPlugin(useGSAP);

// ─── Props ───────────────────────────────────────────────────────────────────

interface VersionStripProps {
  versions: Version[];
  activeVersionId: string | null;
  onSelectVersion: (versionId: string) => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Returns a relative timestamp string (e.g., "2m ago").
 */
function getRelativeTime(timestamp: number): string {
  return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
}

/**
 * Truncates a revision note to approximately 20 characters.
 */
function truncateNote(note: string, maxLength = 20): string {
  if (note.length <= maxLength) return note;
  return note.slice(0, maxLength).trimEnd() + "…";
}

// ─── Component ───────────────────────────────────────────────────────────────

export function VersionStrip({
  versions,
  activeVersionId,
  onSelectVersion,
}: VersionStripProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(true);

  // Animate version items on mount / when versions change
  useGSAP(
    () => {
      if (versions.length === 0 || !expanded) return;
      gsap.from(".version-item", {
        x: -20,
        autoAlpha: 0,
        stagger: 0.08,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [versions.length, expanded] }
  );

  // Don't render if no versions exist
  if (versions.length === 0) return null;

  return (
    <div ref={containerRef} className="space-y-2">
      {/* Section header — collapsible toggle */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        aria-controls="version-history-strip"
        className={cn(
          "flex w-full items-center justify-between text-sm font-medium text-muted-foreground transition-colors",
          "hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-md px-1 py-1"
        )}
      >
        <span>Version History</span>
        {expanded ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>

      {/* Horizontal scrollable strip */}
      <div
        id="version-history-strip"
        role="list"
        aria-label="Version history"
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          expanded ? "max-h-[200px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="flex gap-3 overflow-x-auto pb-2">
          {versions.map((version) => {
            const isActive = version.id === activeVersionId;
            const isImage = version.templateType !== "text_copy";

            return (
              <button
                key={version.id}
                type="button"
                role="listitem"
                tabIndex={0}
                onClick={() => onSelectVersion(version.id)}
                aria-label={`${version.label}${version.revisionNote ? `, ${version.revisionNote}` : ""}`}
                aria-current={isActive ? "true" : undefined}
                className={cn(
                  "version-item flex-shrink-0 flex flex-col items-center gap-1 rounded-lg border p-2 transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  "hover:bg-accent/50 cursor-pointer",
                  isActive
                    ? "border-blue-500 ring-2 ring-blue-500/30 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-400"
                    : "border-border bg-card"
                )}
              >
                {/* Thumbnail area */}
                <div className="flex h-12 w-12 items-center justify-center rounded-md bg-muted">
                  {isImage && version.publicUrl ? (
                    <img
                      src={version.publicUrl}
                      alt={`${version.label} thumbnail`}
                      className="h-12 w-12 rounded-md object-cover"
                    />
                  ) : isImage ? (
                    <Image className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <Type className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>

                {/* Version label */}
                <span className="text-xs font-semibold text-foreground">
                  {version.label}
                </span>

                {/* Relative timestamp */}
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                  {getRelativeTime(version.timestamp)}
                </span>

                {/* Revision note (truncated) */}
                {version.revisionNote && (
                  <span
                    className="text-[10px] text-muted-foreground/70 max-w-[72px] truncate"
                    title={version.revisionNote}
                  >
                    {truncateNote(version.revisionNote)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
