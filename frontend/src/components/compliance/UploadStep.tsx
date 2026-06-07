import { UploadForm } from "@/components/compliance/UploadForm";
import { Button } from "@/components/ui/button";
import type { UploadParams } from "@/types/compliance";

interface UploadStepProps {
  onSubmit: (params: UploadParams) => void;
  isSubmitting: boolean;
  error: { message: string; retryable: boolean } | null;
  onRetry: () => void;
}

export function UploadStep({
  onSubmit,
  isSubmitting,
  error,
  onRetry,
}: UploadStepProps) {
  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div
          className="p-4 bg-error-container rounded-xl flex items-center justify-between"
          role="alert"
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-on-error-container">
              error
            </span>
            <p className="text-on-error-container font-label-ui text-label-ui">
              {error.message}
            </p>
          </div>
          {error.retryable && (
            <Button onClick={onRetry} variant="default" size="sm">
              Retry
            </Button>
          )}
        </div>
      )}
      <UploadForm onSubmit={onSubmit} isSubmitting={isSubmitting} />
    </div>
  );
}
