/**
 * CanvasToolbar — Run and Save buttons for the Generation Canvas.
 */

import { Play, Save, Loader2 } from "lucide-react";

interface CanvasToolbarProps {
  onRun: () => void;
  onSave: () => void;
  isRunning: boolean;
  isSaving: boolean;
}

export function CanvasToolbar({ onRun, onSave, isRunning, isSaving }: CanvasToolbarProps) {
  return (
    <div className="flex items-center gap-2 border-b bg-background px-4 py-2">
      <button
        className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        onClick={onRun}
        disabled={isRunning}
      >
        {isRunning ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Play className="h-3.5 w-3.5" />
        )}
        {isRunning ? "Running..." : "Run Pipeline"}
      </button>
      <button
        className="flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-50"
        onClick={onSave}
        disabled={isSaving}
      >
        {isSaving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Save className="h-3.5 w-3.5" />
        )}
        Save
      </button>
    </div>
  );
}

export default CanvasToolbar;
