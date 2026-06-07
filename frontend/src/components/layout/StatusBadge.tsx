import { cn } from "@/lib/utils";

type BadgeStatus = "draft" | "active" | "review" | "passed" | "error" | "warning";

interface StatusBadgeProps {
  status: BadgeStatus;
  size?: "sm" | "md";
}

const statusStyles: Record<BadgeStatus, string> = {
  draft: "bg-gray-100 dark:bg-white/5 text-gray-500",
  active: "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600",
  review: "bg-amber-50 dark:bg-amber-950/20 text-amber-600",
  passed: "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600",
  warning: "bg-amber-50 dark:bg-amber-950/20 text-amber-600",
  error: "bg-red-50 dark:bg-red-950/20 text-red-600",
};

const statusLabels: Record<BadgeStatus, string> = {
  draft: "Draft",
  active: "Active",
  review: "Review",
  passed: "Passed",
  warning: "Warning",
  error: "Error",
};

const sizeStyles = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-sm",
} as const;

/**
 * Status/severity badge using accent tokens.
 * Maps status to fixed background/text color pairs per Requirement 7.
 */
export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium capitalize",
        statusStyles[status],
        sizeStyles[size]
      )}
    >
      {statusLabels[status]}
    </span>
  );
}
