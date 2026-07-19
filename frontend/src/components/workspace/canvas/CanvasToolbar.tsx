/**
 * CanvasToolbar — Minimal toolbar for the Generation Canvas.
 * Save is now Ctrl+S (no button). Run Pipeline was removed (runs on chat send).
 * Shows a Settings gear icon and a mode toggle to switch back to Easy Mode.
 */

import { Settings, Loader2 } from "lucide-react";
import { useNavigate } from "react-router";

interface CanvasToolbarProps {
  projectId: string;
  taskId: string;
  isSaving: boolean;
  onOpenSettings: () => void;
}

export function CanvasToolbar({ projectId, taskId, isSaving, onOpenSettings }: CanvasToolbarProps) {
  const navigate = useNavigate();

  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center border-b bg-background px-4 py-2">
      <div>
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide select-none">
          Generation Canvas
        </span>
      </div>

      {/* Match the Easy Mode switcher and keep it centred in the workspace. */}
      <div className="flex w-[360px] max-w-full rounded-lg border border-border-default bg-surface-card p-1 shadow-sm">
          <button
            type="button"
            onClick={() => navigate(`/dashboard/project/${projectId}/easy/${taskId}`)}
            className="flex-1 rounded-md px-6 py-1.5 text-center text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
          >
            Easy Mode
          </button>
          <span className="flex-1 rounded-md bg-primary px-6 py-1.5 text-center text-xs font-semibold text-primary-foreground shadow-sm">
            Advanced Mode
          </span>
      </div>

      <div className="flex items-center justify-end gap-2">
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
