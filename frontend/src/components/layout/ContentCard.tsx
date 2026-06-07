import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ContentCardProps {
  children: ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
}

const paddingMap = {
  sm: "p-4",
  md: "p-5",
  lg: "p-6",
} as const;

/**
 * Themed card container with consistent radius, shadow, and border.
 * Uses bg-surface-card, border-border-default, rounded-2xl, and card-shadow.
 */
export function ContentCard({
  children,
  className,
  padding = "md",
}: ContentCardProps) {
  if (!children) {
    if (import.meta.env.DEV) {
      console.warn("ContentCard: `children` prop is required");
    }
    return null;
  }

  return (
    <div
      className={cn(
        "rounded-2xl border border-border-default bg-surface-card card-shadow",
        paddingMap[padding],
        className
      )}
    >
      {children}
    </div>
  );
}
