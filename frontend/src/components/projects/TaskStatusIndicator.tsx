/**
 * TaskStatusIndicator — Renders a colored dot + label for task execution status.
 * Maps status to semantic accent colors following the design system.
 */

import { cn } from "@/lib/utils";
import type { TaskStatus } from "./types";

interface TaskStatusIndicatorProps {
  status: TaskStatus;
}

const STATUS_CONFIG: Record<TaskStatus, { color: string; dotClass: string; label: string }> = {
  completed: {
    color: "text-accent-emerald",
    dotClass: "bg-accent-emerald",
    label: "Completed",
  },
  failed: {
    color: "text-accent-error",
    dotClass: "bg-accent-error animate-pulse",
    label: "Failed",
  },
  processing: {
    color: "text-accent-amber",
    dotClass: "bg-accent-amber animate-pulse",
    label: "Processing",
  },
};

export function TaskStatusIndicator({ status }: TaskStatusIndicatorProps) {
  const config = STATUS_CONFIG[status];

  return (
    <div className={cn("flex items-center gap-2", config.color)}>
      <span className={cn("w-2 h-2 rounded-full", config.dotClass)} />
      <span className="text-label-ui font-medium">{config.label}</span>
    </div>
  );
}
