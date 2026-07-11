/**
 * ErrorDisplay — Inline error component rendered in the PreviewPanel area
 * when generation fails. Provides Retry, Edit Inputs, and Dismiss actions.
 *
 * Requirements: 16.1, 16.2, 16.3, 16.4, 15.1, 15.3, 19.3
 */

import { useRef, useEffect } from "react";
import { AlertTriangle, RefreshCw, PencilLine, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { GenerationError } from "@/types/easyGeneration";

// ─── Props ───────────────────────────────────────────────────────────────────

interface ErrorDisplayProps {
  error: GenerationError;
  onRetry: () => void;
  onEditInputs: () => void;
  onDismiss: () => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function ErrorDisplay({
  error,
  onRetry,
  onEditInputs,
  onDismiss,
}: ErrorDisplayProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-focus the error container when it appears (Req 15.3)
  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  return (
    <Card className="border-destructive/50 bg-destructive/5">
      <CardContent className="p-4">
        <div
          ref={containerRef}
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          tabIndex={-1}
          className="flex flex-col gap-4 outline-none"
        >
          {/* Error message */}
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-destructive">
                Generation failed
              </p>
              <p className="text-sm text-muted-foreground">
                {error.message}
              </p>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {error.retryable && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={onEditInputs}
            >
              <PencilLine className="h-3.5 w-3.5" />
              Edit Inputs
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onDismiss}
            >
              <X className="h-3.5 w-3.5" />
              Dismiss
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
