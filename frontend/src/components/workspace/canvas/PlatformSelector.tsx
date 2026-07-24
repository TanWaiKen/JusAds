import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Music2 } from "lucide-react";
import { DEFAULT_PLATFORM, type TargetPlatform } from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

export { DEFAULT_PLATFORM };
export type { TargetPlatform };

// Custom inline Instagram SVG icon to bypass local lucide-react package version mismatches
function Instagram({ size = 24, className = "" }: { size?: number | string; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
    </svg>
  );
}

// Custom Shopee icon (shopping bag)
function ShopeeIcon({ size = 24, className = "" }: { size?: number | string; className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
      <path d="M3 6h18" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </svg>
  );
}

interface PlatformOption {
  value: TargetPlatform;
  label: string;
  icon: React.ComponentType<{ size?: number | string; className?: string }>;
}

/** Supported platform options for the Malaysian market. */
const PLATFORM_OPTIONS: readonly PlatformOption[] = [
  { value: "tiktok", label: "TikTok", icon: Music2 },
  { value: "instagram", label: "Instagram", icon: Instagram },
  { value: "shopee", label: "Shopee", icon: ShopeeIcon },
];

interface PlatformSelectorProps {
  /** Currently selected platform, or `null` when nothing is selected. */
  selected: TargetPlatform | null;
  /** Called with the platform when the user picks one. */
  onSelect: (platform: TargetPlatform) => void;
}

/**
 * Single-select platform picker for the generation canvas.
 *
 * Presentation only — it MUST NOT compute size, aspect-ratio, or ad-length
 * values (Req 9.4). It surfaces the selected platform (Req 9.3) and, when
 * nothing is selected, indicates that Instagram is the default that applies
 * (Req 9.5).
 */
export function PlatformSelector({ selected, onSelect }: PlatformSelectorProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);

  // Only the click micro-interaction uses GSAP. The entrance animation is
  // removed because this component renders inside an already-animated parent
  // (SettingsPanel), and nested autoAlpha animations cause visibility glitches.
  const { contextSafe } = useGSAP(() => {}, { scope: containerRef });

  const handleSelect = contextSafe((option: PlatformOption, target: HTMLButtonElement) => {
    gsap.fromTo(
      target,
      { scale: 0.94 },
      { scale: 1, duration: 0.25, ease: "power1.inOut" }
    );
    onSelect(option.value);
  });

  return (
    <div ref={containerRef} className="flex flex-col gap-1.5 w-full">
      <div
        className="grid grid-cols-2 gap-1 p-1 bg-muted/40 rounded-lg border border-border w-full"
        role="radiogroup"
        aria-label="Target platform"
      >
        {PLATFORM_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isSelected = selected === option.value;

          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={(e) => handleSelect(option, e.currentTarget)}
              className={`platform-option flex items-center justify-center gap-2 py-2 px-3 text-xs rounded-md transition-all cursor-pointer ${
                isSelected
                  ? "bg-background text-foreground font-semibold shadow-sm border border-border"
                  : "text-muted-foreground hover:text-foreground font-medium"
              }`}
            >
              <Icon size={14} className={isSelected ? "text-primary" : "text-muted-foreground"} />
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>

      {selected !== null && (
        <p className="text-[11px] text-muted-foreground">
          Selected:{" "}
          <span className="font-medium text-foreground">
            {PLATFORM_OPTIONS.find((o) => o.value === selected)?.label}
          </span>
        </p>
      )}
    </div>
  );
}

export default PlatformSelector;
