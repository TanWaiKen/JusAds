/**
 * PreviewPanel — Center column displaying generated asset previews, loading
 * states with progressive status text, and aspect-ratio-appropriate placeholders.
 *
 * Requirements: 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 15.2, 19.1, 19.2, 19.4
 */

import { useState, useEffect, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Loader2, ChevronLeft, ChevronRight, ImageIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { ErrorDisplay } from "@/components/easy-generation/ErrorDisplay";
import type { TemplateType, EasyGenerationState, GenerationError, Version } from "@/types/easyGeneration";

gsap.registerPlugin(useGSAP);

// ─── Props ───────────────────────────────────────────────────────────────────

interface PreviewPanelProps {
  selectedTemplate: TemplateType | null;
  generationStatus: EasyGenerationState["generationStatus"];
  statusText: string;
  generationStartTime: number | null;
  activeVersion: Version | null;
  comparisonVersion: Version | null;
  error: GenerationError | null;
  onSelectVersion: (versionId: string) => void;
  onRetry: () => void;
  onEditInputs: () => void;
  onDismiss: () => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Returns the Tailwind aspect-ratio class for a template type. */
function getAspectClass(template: TemplateType): string {
  switch (template) {
    case "poster":
      return "aspect-square";
    case "story":
      return "aspect-[9/16]";
    case "carousel":
      return "aspect-square";
    case "text_copy":
      return "";
  }
}

/** Returns a max-width class to prevent overly wide containers for tall ratios. */
function getContainerMaxWidth(template: TemplateType): string {
  switch (template) {
    case "story":
      return "max-w-[320px]";
    default:
      return "max-w-[480px]";
  }
}

// ─── Sub-Components ──────────────────────────────────────────────────────────

/** Empty state — no template selected yet. */
function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-center">
        <ImageIcon className="h-12 w-12 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          Select a template to get started
        </p>
      </div>
    </div>
  );
}

/** Idle state — template selected but generation not started. */
function IdleState({ template }: { template: TemplateType }) {
  const aspectClass = getAspectClass(template);

  if (template === "text_copy") {
    return (
      <div className="flex min-h-[200px] items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/20 bg-muted/30 p-8">
        <p className="text-sm text-muted-foreground">Ready to generate</p>
      </div>
    );
  }

  return (
    <div
      className={`${aspectClass} flex w-full items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/20 bg-muted/30`}
    >
      <p className="text-sm text-muted-foreground">Ready to generate</p>
    </div>
  );
}

/** Loading state — generation in progress. */
function LoadingState({
  template,
  statusText,
  generationStartTime,
}: {
  template: TemplateType;
  statusText: string;
  generationStartTime: number | null;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!generationStartTime) return;

    const interval = setInterval(() => {
      setElapsed(Date.now() - generationStartTime);
    }, 500);

    return () => clearInterval(interval);
  }, [generationStartTime]);

  const showProgress = elapsed >= 5000;
  const aspectClass = getAspectClass(template);

  // Indeterminate progress value — pulses between 10-90 during generation
  const progressValue = showProgress
    ? Math.min(90, 10 + ((elapsed - 5000) / 60000) * 80)
    : null;

  if (template === "text_copy") {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-lg bg-muted/20 p-8">
        {showProgress ? (
          <ProgressDisplay statusText={statusText} progressValue={progressValue} />
        ) : (
          <SpinnerDisplay statusText={statusText} />
        )}
      </div>
    );
  }

  return (
    <div
      className={`${aspectClass} flex w-full flex-col items-center justify-center gap-4 rounded-lg bg-muted/20`}
    >
      {showProgress ? (
        <ProgressDisplay statusText={statusText} progressValue={progressValue} />
      ) : (
        <SpinnerDisplay statusText={statusText} />
      )}
    </div>
  );
}

/** Spinner shown for first 5 seconds of generation. */
function SpinnerDisplay({ statusText }: { statusText: string }) {
  return (
    <div className="flex flex-col items-center gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      {statusText && (
        <p className="text-sm text-muted-foreground">{statusText}</p>
      )}
    </div>
  );
}

/** Progress indicator shown after 5 seconds of generation. */
function ProgressDisplay({
  statusText,
  progressValue,
}: {
  statusText: string;
  progressValue: number | null;
}) {
  return (
    <div className="flex w-full max-w-[240px] flex-col items-center gap-3">
      <Progress value={progressValue} />
      {statusText && (
        <p className="text-sm font-medium text-muted-foreground">{statusText}</p>
      )}
    </div>
  );
}

/** Renders a generated image asset at the correct aspect ratio. */
function ImageAsset({
  version,
  template,
}: {
  version: Version;
  template: TemplateType;
}) {
  const aspectClass = getAspectClass(template);

  return (
    <div className={`${aspectClass} w-full overflow-hidden rounded-lg bg-muted/10`}>
      <img
        src={version.publicUrl ?? ""}
        alt={`Generated ${template} — ${version.label}`}
        className="h-full w-full object-contain"
      />
    </div>
  );
}

/** Renders a carousel asset with navigation arrows and index dots. */
function CarouselAsset({ version }: { version: Version }) {
  const [currentSlide, setCurrentSlide] = useState(0);

  // For carousel, publicUrl points to the first slide. Additional slides
  // are inferred by appending _2, _3, etc. For now we render the single
  // image with nav UI placeholders. The parent page can extend once the
  // multi-slide URL scheme is confirmed.
  const slides = version.publicUrl ? [version.publicUrl] : [];

  const handlePrev = () => {
    setCurrentSlide((prev) => (prev > 0 ? prev - 1 : slides.length - 1));
  };

  const handleNext = () => {
    setCurrentSlide((prev) => (prev < slides.length - 1 ? prev + 1 : 0));
  };

  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-muted/10">
      {slides.length > 0 && (
        <img
          src={slides[currentSlide]}
          alt={`Carousel slide ${currentSlide + 1} of ${slides.length} — ${version.label}`}
          className="h-full w-full object-contain"
        />
      )}

      {/* Navigation arrows */}
      {slides.length > 1 && (
        <>
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 shadow-sm"
            onClick={handlePrev}
            aria-label="Previous slide"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 shadow-sm"
            onClick={handleNext}
            aria-label="Next slide"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </>
      )}

      {/* Slide indicator dots */}
      {slides.length > 1 && (
        <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 gap-1.5">
          {slides.map((_, index) => (
            <span
              key={index}
              className={`h-2 w-2 rounded-full transition-colors ${
                index === currentSlide
                  ? "bg-primary"
                  : "bg-muted-foreground/30"
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** Renders a text_copy asset as a formatted text block in a card. */
function TextAsset({ version }: { version: Version }) {
  return (
    <Card>
      <CardContent>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
          {version.caption ?? ""}
        </p>
      </CardContent>
    </Card>
  );
}

/** Renders the correct asset type based on template. */
function AssetRenderer({
  version,
  template,
}: {
  version: Version;
  template: TemplateType;
}) {
  switch (template) {
    case "poster":
    case "story":
      return <ImageAsset version={version} template={template} />;
    case "carousel":
      return <CarouselAsset version={version} />;
    case "text_copy":
      return <TextAsset version={version} />;
  }
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function PreviewPanel({
  selectedTemplate,
  generationStatus,
  statusText,
  generationStartTime,
  activeVersion,
  comparisonVersion,
  error,
  onSelectVersion,
  onRetry,
  onEditInputs,
  onDismiss,
}: PreviewPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (generationStatus === "completed" && activeVersion) {
        gsap.from(".preview-asset", {
          y: 20,
          autoAlpha: 0,
          duration: 0.5,
          ease: "power2.out",
        });
      }
    },
    { scope: containerRef, dependencies: [generationStatus, activeVersion?.id] }
  );

  // Determine which view to render
  const renderContent = () => {
    // Empty state — no template selected
    if (!selectedTemplate) {
      return <EmptyState />;
    }

    // Generating state
    if (generationStatus === "generating") {
      return (
        <LoadingState
          template={selectedTemplate}
          statusText={statusText}
          generationStartTime={generationStartTime}
        />
      );
    }

    // Failed state — display inline error with recovery actions
    if (generationStatus === "failed" && error) {
      return (
        <ErrorDisplay
          error={error}
          onRetry={onRetry}
          onEditInputs={onEditInputs}
          onDismiss={onDismiss}
        />
      );
    }

    // Completed — comparison mode (two versions side by side)
    if (
      generationStatus === "completed" &&
      activeVersion &&
      comparisonVersion
    ) {
      return (
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <div className="preview-asset">
              <AssetRenderer
                version={activeVersion}
                template={selectedTemplate}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {activeVersion.label}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSelectVersion(activeVersion.id)}
              >
                Use this
              </Button>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <div className="preview-asset">
              <AssetRenderer
                version={comparisonVersion}
                template={selectedTemplate}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {comparisonVersion.label}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSelectVersion(comparisonVersion.id)}
              >
                Use this
              </Button>
            </div>
          </div>
        </div>
      );
    }

    // Completed — single version display
    if (generationStatus === "completed" && activeVersion) {
      return (
        <div className="preview-asset">
          <AssetRenderer version={activeVersion} template={selectedTemplate} />
        </div>
      );
    }

    // Idle state — template selected but no generation started
    return <IdleState template={selectedTemplate} />;
  };

  const containerMaxWidth = selectedTemplate
    ? getContainerMaxWidth(selectedTemplate)
    : "max-w-[480px]";

  return (
    <div
      ref={containerRef}
      className="flex h-full flex-col items-center justify-center p-4"
    >
      {/* aria-live region for screen reader announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        role="status"
      >
        {generationStatus === "generating" && statusText}
        {generationStatus === "completed" && "Generation complete"}
        {generationStatus === "failed" && error && `Generation failed: ${error.message}`}
      </div>

      <div className={`w-full ${containerMaxWidth}`}>{renderContent()}</div>
    </div>
  );
}
