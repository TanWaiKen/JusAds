import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import type { AdvancedOptions } from "@/types/easyGeneration";
import { cn } from "@/lib/utils";

// ─── Props ───────────────────────────────────────────────────────────────────

interface AdvancedDrawerProps {
  advancedOptions: AdvancedOptions;
  onOptionsChange: (options: Partial<AdvancedOptions>) => void;
}

// ─── Toggle Button Group ─────────────────────────────────────────────────────

interface ToggleOption<T extends string> {
  value: T;
  label: string;
}

interface ToggleButtonGroupProps<T extends string> {
  options: ToggleOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  id: string;
}

function ToggleButtonGroup<T extends string>({
  options,
  value,
  onChange,
  label,
  id,
}: ToggleButtonGroupProps<T>) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-sm">
        {label}
      </Label>
      <div
        id={id}
        role="radiogroup"
        aria-label={label}
        className="flex gap-1.5"
      >
        {options.map((option) => {
          const isActive = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => onChange(option.value)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isActive
                  ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:border-blue-400 dark:text-blue-300"
                  : "border-border bg-card text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export function AdvancedDrawer({ advancedOptions, onOptionsChange }: AdvancedDrawerProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-border">
      {/* Collapsed header / toggle */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        aria-controls="advanced-options-panel"
        className={cn(
          "flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-muted-foreground transition-colors",
          "hover:text-foreground hover:bg-accent/30 rounded-xl",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        )}
      >
        <span>Need more control?</span>
        {expanded ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>

      {/* Expandable content with smooth height transition */}
      <div
        id="advanced-options-panel"
        role="region"
        aria-labelledby="advanced-drawer-toggle"
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          expanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="space-y-4 px-4 pb-4">
          {/* Quality */}
          <ToggleButtonGroup
            id="advanced-quality"
            label="Quality"
            options={[
              { value: "standard", label: "Standard" },
              { value: "high", label: "High" },
            ]}
            value={advancedOptions.quality}
            onChange={(val) => onOptionsChange({ quality: val })}
          />

          {/* Style Strength */}
          <ToggleButtonGroup
            id="advanced-style-strength"
            label="Style Strength"
            options={[
              { value: "low", label: "Low" },
              { value: "medium", label: "Medium" },
              { value: "high", label: "High" },
            ]}
            value={advancedOptions.styleStrength}
            onChange={(val) => onOptionsChange({ styleStrength: val })}
          />

          {/* Keep Layout */}
          <ToggleButtonGroup
            id="advanced-keep-layout"
            label="Keep Layout Close to Original"
            options={[
              { value: "yes", label: "Yes" },
              { value: "no", label: "No" },
            ]}
            value={advancedOptions.keepLayout ? "yes" : "no"}
            onChange={(val) => onOptionsChange({ keepLayout: val === "yes" })}
          />

          {/* Extra Instructions */}
          <div className="space-y-1.5">
            <Label htmlFor="advanced-extra-instructions" className="text-sm">
              Extra Instructions
            </Label>
            <Textarea
              id="advanced-extra-instructions"
              value={advancedOptions.extraInstructions}
              placeholder="Add any specific instructions..."
              onChange={(e) =>
                onOptionsChange({ extraInstructions: e.target.value })
              }
              className="min-h-20 resize-none"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
