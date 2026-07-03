/**
 * CanvasToolbar — Minimal toolbar for the Generation Canvas.
 * Save is now Ctrl+S (no button). Run Pipeline was removed (runs on chat send).
 * Only shows a Settings gear icon.
 */

import { Settings, Loader2 } from "lucide-react";

interface CanvasToolbarProps {
  isSaving: boolean;
  onOpenSettings: () => void;
}

export function CanvasToolbar({ isSaving, onOpenSettings }: CanvasToolbarProps) {
  return (
    <div className="flex items-center justify-between border-b bg-background px-4 py-2">
      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide select-none">
        Generation Canvas
      </span>
      <div className="flex items-center gap-2">
        {isSaving && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Saving…
          </span>
        )}
        <button
          type="button"
          onClick={onOpenSettings}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border bg-background text-foreground hover:bg-accent transition-colors cursor-pointer"
          title="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export default CanvasToolbar;
