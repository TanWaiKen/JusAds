import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Image, Smartphone, GalleryHorizontalEnd, Type } from "lucide-react";
import { TEMPLATE_CONFIGS, type TemplateType } from "@/types/easyGeneration";
import { cn } from "@/lib/utils";

gsap.registerPlugin(useGSAP);

// ─── Icon Mapping ────────────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  image: Image,
  smartphone: Smartphone,
  "gallery-horizontal-end": GalleryHorizontalEnd,
  type: Type,
};

// ─── Props ───────────────────────────────────────────────────────────────────

interface TemplateSelectorProps {
  selectedTemplate: TemplateType | null;
  onSelect: (template: TemplateType) => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function TemplateSelector({ selectedTemplate, onSelect }: TemplateSelectorProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".template-card", {
      y: 30,
      autoAlpha: 0,
      stagger: 0.08,
      duration: 0.4,
      ease: "power2.out",
    });
  }, { scope: containerRef });

  const templates = Object.values(TEMPLATE_CONFIGS);

  return (
    <div ref={containerRef} className="grid grid-cols-2 gap-3">
      {templates.map((config) => {
        const Icon = ICON_MAP[config.icon];
        const isActive = selectedTemplate === config.id;

        return (
          <button
            key={config.id}
            type="button"
            onClick={() => onSelect(config.id)}
            className={cn(
              "template-card flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-colors",
              "hover:bg-accent/50 hover:border-accent-foreground/20",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              isActive
                ? "border-blue-500 bg-blue-50 ring-2 ring-blue-500/30 dark:bg-blue-950/30 dark:border-blue-400"
                : "border-border bg-card"
            )}
            aria-pressed={isActive}
          >
            <div className={cn(
              "flex h-9 w-9 items-center justify-center rounded-lg",
              isActive
                ? "bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400"
                : "bg-muted text-muted-foreground"
            )}>
              {Icon && <Icon className="h-5 w-5" />}
            </div>

            <div className="space-y-0.5">
              <span className={cn(
                "text-sm font-medium leading-none",
                isActive ? "text-blue-700 dark:text-blue-300" : "text-foreground"
              )}>
                {config.label}
              </span>
              <p className="text-xs text-muted-foreground leading-snug">
                {config.description}
              </p>
            </div>

            <span className={cn(
              "mt-auto inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium",
              isActive
                ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
                : "bg-muted text-muted-foreground"
            )}>
              {config.aspectRatio}
            </span>
          </button>
        );
      })}
    </div>
  );
}
