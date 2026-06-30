/**
 * TaskTypeBadge — Compact pill badge showing the task type (Generation, Compliance, Remix).
 * Sized to align with Task ID mono font.
 */

import { cn } from "@/lib/utils";
import type { TaskType } from "./types";

interface TaskTypeBadgeProps {
  type: TaskType;
}

const TYPE_CONFIG: Record<TaskType, { bg: string; text: string; label: string }> = {
  generation: {
    bg: "bg-accent-blue/5",
    text: "text-accent-blue",
    label: "Generation",
  },
  compliance: {
    bg: "bg-accent-pink/5",
    text: "text-accent-pink",
    label: "Compliance",
  },
  remix: {
    bg: "bg-accent-amber/5",
    text: "text-accent-amber",
    label: "Remix",
  },
};

export function TaskTypeBadge({ type }: TaskTypeBadgeProps) {
  const config = TYPE_CONFIG[type];

  return (
    <span
      className={cn(
        "inline-flex px-1.5 py-0.5 rounded font-jetbrains text-[11px] uppercase font-medium leading-tight",
        config.bg,
        config.text
      )}
    >
      {config.label}
    </span>
  );
}
