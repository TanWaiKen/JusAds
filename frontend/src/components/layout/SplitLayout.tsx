import type { ReactNode } from "react";

interface SplitLayoutProps {
  left: ReactNode;
  center?: ReactNode;
  right: ReactNode;
  leftWidth?: string;
  rightWidth?: string;
}

/**
 * Configurable two or three column layout.
 * Uses bg-surface-panel for side panels.
 * Collapses to vertical stack below lg breakpoint (1024px).
 */
export function SplitLayout({
  left,
  center,
  right,
  leftWidth = "280px",
  rightWidth = "320px",
}: SplitLayoutProps) {
  const isThreeColumn = !!center;

  return (
    <div className="flex h-full flex-col lg:flex-row">
      {/* Left panel */}
      <aside
        className="w-full shrink-0 border-b border-border-default bg-surface-panel lg:border-b-0 lg:border-r"
        style={
          { "--split-left-w": leftWidth } as React.CSSProperties
        }
      >
        <div className="h-full w-full overflow-y-auto lg:w-[var(--split-left-w)]">
          {left}
        </div>
      </aside>

      {/* Center content (present in 3-col layout) */}
      {isThreeColumn ? (
        <>
          <main className="min-w-0 flex-1 overflow-y-auto">
            {center}
          </main>
          <aside
            className="w-full shrink-0 border-t border-border-default bg-surface-panel lg:border-l lg:border-t-0"
            style={
              { "--split-right-w": rightWidth } as React.CSSProperties
            }
          >
            <div className="h-full w-full overflow-y-auto lg:w-[var(--split-right-w)]">
              {right}
            </div>
          </aside>
        </>
      ) : (
        /* Two-column: right side is main content */
        <main className="min-w-0 flex-1 overflow-y-auto">
          {right}
        </main>
      )}
    </div>
  );
}
