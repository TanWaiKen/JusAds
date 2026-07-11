/**
 * FeedbackSidebar — Right panel containing metadata summary, revision input,
 * and version history strip. Supports feedback-based regeneration where
 * revision instructions are stored separately from form values (Property 6).
 *
 * Requirements: 7.1, 9.1, 9.2, 9.3, 9.4, 10.1
 */

import { useState, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Send } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { VersionStrip } from "@/components/easy-generation/VersionStrip";
import type { Version, EasyGenerationState } from "@/types/easyGeneration";
import { TEMPLATE_CONFIGS } from "@/types/easyGeneration";

gsap.registerPlugin(useGSAP);

// ─── Props ───────────────────────────────────────────────────────────────────

interface FeedbackSidebarProps {
  activeVersion: Version | null;
  versions: Version[];
  activeVersionId: string | null;
  generationStatus: EasyGenerationState["generationStatus"];
  onSubmitRevision: (instruction: string) => void;
  onSelectVersion: (versionId: string) => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleString([], {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function formatDuration(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

function getTemplateLabel(templateType: Version["templateType"]): string {
  return TEMPLATE_CONFIGS[templateType]?.label ?? templateType;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function FeedbackSidebar({
  activeVersion,
  versions,
  activeVersionId,
  generationStatus,
  onSubmitRevision,
  onSelectVersion,
}: FeedbackSidebarProps) {
  const [revisionText, setRevisionText] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const isGenerating = generationStatus === "generating";
  const isSubmitDisabled = !revisionText.trim() || isGenerating;

  useGSAP(
    () => {
      if (!activeVersion) return;
      gsap.from(".metadata-section", {
        y: 10,
        autoAlpha: 0,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [activeVersion?.id] }
  );

  function handleSubmit() {
    const instruction = revisionText.trim();
    if (!instruction) return;
    // Property 6: Revision instruction stored separately — NOT merged into form values.
    // The onSubmitRevision callback passes the instruction to the parent which
    // triggers a new generation cycle with the revision alongside original form inputs.
    onSubmitRevision(instruction);
    setRevisionText("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !isSubmitDisabled) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div ref={containerRef} className="flex h-full flex-col overflow-y-auto">
      <div className="flex flex-1 flex-col gap-6 p-4">
        {/* Metadata Summary — visible when a version is active */}
        {activeVersion && (
          <section className="metadata-section flex flex-col gap-3">
            <h2 className="text-sm font-medium text-foreground">
              Generation Details
            </h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <dt className="text-muted-foreground">Template</dt>
              <dd className="font-medium text-foreground">
                {getTemplateLabel(activeVersion.templateType)}
              </dd>

              <dt className="text-muted-foreground">Dimensions</dt>
              <dd className="font-medium text-foreground">
                {activeVersion.dimensions}
              </dd>

              <dt className="text-muted-foreground">Platform</dt>
              <dd className="font-medium text-foreground">
                {activeVersion.platform}
              </dd>

              <dt className="text-muted-foreground">Generated at</dt>
              <dd className="font-medium text-foreground">
                {formatTimestamp(activeVersion.timestamp)}
              </dd>

              <dt className="text-muted-foreground">Duration</dt>
              <dd className="font-medium text-foreground">
                {formatDuration(activeVersion.generationDuration)}
              </dd>
            </dl>
          </section>
        )}

        {/* Revision Input */}
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium text-foreground">
            Refine your ad
          </h2>
          <Textarea
            value={revisionText}
            onChange={(e) => setRevisionText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe changes... (e.g., 'make it more blue', 'use festive Malay style')"
            className="min-h-[80px] resize-none text-sm"
            aria-label="Revision instructions"
          />
          <Button
            variant="default"
            size="default"
            className="w-full"
            disabled={isSubmitDisabled}
            onClick={handleSubmit}
          >
            <Send className="h-4 w-4" />
            Refine
          </Button>
          <p className="text-[11px] text-muted-foreground">
            Press Ctrl+Enter to submit
          </p>
        </section>
      </div>

      {/* Version Strip — fixed at bottom */}
      <div className="border-t border-border p-4">
        <VersionStrip
          versions={versions}
          activeVersionId={activeVersionId}
          onSelectVersion={onSelectVersion}
        />
      </div>
    </div>
  );
}
