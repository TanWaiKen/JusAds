import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TEMPLATE_CONFIGS, type Version } from "@/types/easyGeneration";
import { cn } from "@/lib/utils";

gsap.registerPlugin(useGSAP);

// ─── Props ───────────────────────────────────────────────────────────────────

interface ComparisonViewProps {
  activeVersion: Version;
  comparisonVersion: Version;
  onSelectVersion: (versionId: string) => void;
}

// ─── Aspect Ratio Helpers ────────────────────────────────────────────────────

function getAspectRatioClass(templateType: Version["templateType"]): string {
  const config = TEMPLATE_CONFIGS[templateType];
  switch (config.aspectRatio) {
    case "1:1":
      return "aspect-square";
    case "9:16":
      return "aspect-[9/16]";
    default:
      return "";
  }
}

// ─── Version Card Sub-Component ──────────────────────────────────────────────

interface VersionCardProps {
  version: Version;
  onSelect: () => void;
}

function VersionCard({ version, onSelect }: VersionCardProps) {
  const isTextCopy = version.templateType === "text_copy";
  const aspectClass = getAspectRatioClass(version.templateType);

  return (
    <div className="version-card flex flex-col gap-3 rounded-xl border border-border bg-card p-3">
      {/* Asset Display */}
      {isTextCopy ? (
        <div className="rounded-lg bg-muted/50 p-4 min-h-[120px] flex items-center">
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
            {version.caption || "No caption generated"}
          </p>
        </div>
      ) : (
        <div className={cn("w-full overflow-hidden rounded-lg bg-muted", aspectClass)}>
          {version.publicUrl ? (
            <img
              src={version.publicUrl}
              alt={`Generated ${version.templateType} — ${version.label}`}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted-foreground text-xs">
              No image available
            </div>
          )}
        </div>
      )}

      {/* Version Label + Revision Note */}
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center rounded-md bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">
          {version.label}
        </span>
        {version.revisionNote && (
          <span className="truncate text-xs text-muted-foreground">
            {version.revisionNote}
          </span>
        )}
      </div>

      {/* "Use this" Button */}
      <Button
        variant="outline"
        size="sm"
        className="w-full"
        onClick={onSelect}
      >
        <Check className="h-3.5 w-3.5" data-icon="inline-start" />
        Use this
      </Button>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export function ComparisonView({
  activeVersion,
  comparisonVersion,
  onSelectVersion,
}: ComparisonViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".version-card", {
      y: 20,
      autoAlpha: 0,
      stagger: 0.1,
      duration: 0.4,
      ease: "power2.out",
    });
  }, { scope: containerRef });

  return (
    <div
      ref={containerRef}
      className="grid grid-cols-2 gap-4"
      role="group"
      aria-label="Version comparison"
    >
      <VersionCard
        version={activeVersion}
        onSelect={() => onSelectVersion(activeVersion.id)}
      />
      <VersionCard
        version={comparisonVersion}
        onSelect={() => onSelectVersion(comparisonVersion.id)}
      />
    </div>
  );
}
