import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle: string;
  action?: ReactNode;
}

/**
 * Shared page header with title, subtitle, and optional right-side action slot.
 * Uses semantic text tokens for consistent typography across pages.
 */
export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  if (!title) {
    if (import.meta.env.DEV) {
      console.warn("PageHeader: `title` prop is required");
    }
    return null;
  }

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-text-heading">
          {title}
        </h1>
        <p className="text-sm text-text-body">{subtitle}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
