/**
 * CanvasToolbar — Minimal toolbar for the Generation Canvas.
 * Save is now Ctrl+S (no button). Run Pipeline was removed (runs on chat send).
 * Shows a Settings gear icon and a mode toggle to switch back to Easy Mode.
 */

import { Settings, Loader2, Wand2 } from "lucide-react";
import { useNavigate } from "react-router";

interface CanvasToolbarProps {
  projectId: string;
  isSaving: boolean;
  onOpenSettings: () => void;
}

export function CanvasToolbar({ projectId, isSaving, onOpenSettings }: CanvasToolbarProps) {
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-between border-b bg-background px-4 py-2">
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide select-none">
          Generation Canvas
        </span>

        {/* Mode toggle pills */}
        <div className="flex rounded-lg bg-surface-inset p-0.5 border border-border-default">
          <button
            type="button"
            onClick={() => navigate(`/dashboard/project/${projectId}/easy`)}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer text-muted-foreground hover:text-foreground hover:bg-surface-card"
          >
            <Wand2 className="h-3 w-3" />
            Easy
          </button>
          <span className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-md bg-surface-card text-foreground shadow-sm">
            Advanced
          </span>
        </div>
      </div>

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
