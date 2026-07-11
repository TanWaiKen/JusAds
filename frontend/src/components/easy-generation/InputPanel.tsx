/**
 * InputPanel — Container component composing template selection, dynamic form,
 * reference upload, advanced options, and the generate trigger button.
 *
 * Requirements: 1.1, 5.1, 5.2
 */

import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TemplateSelector } from "@/components/easy-generation/TemplateSelector";
import { DynamicForm } from "@/components/easy-generation/DynamicForm";
import { ReferenceUpload } from "@/components/easy-generation/ReferenceUpload";
import { AdvancedDrawer } from "@/components/easy-generation/AdvancedDrawer";
import type { TemplateType, AdvancedOptions, EasyGenerationState } from "@/types/easyGeneration";

// ─── Constants ───────────────────────────────────────────────────────────────

/** Templates that accept reference images for visual style guidance. */
const IMAGE_TEMPLATES: TemplateType[] = ["poster", "story", "carousel"];

// ─── Props ───────────────────────────────────────────────────────────────────

interface InputPanelProps {
  selectedTemplate: TemplateType | null;
  formValues: Record<string, string>;
  advancedOptions: AdvancedOptions;
  referenceUrls: string[];
  generationStatus: EasyGenerationState["generationStatus"];
  onSelectTemplate: (template: TemplateType) => void;
  onFormChange: (values: Record<string, string>) => void;
  onAdvancedChange: (options: Partial<AdvancedOptions>) => void;
  onAddReferenceUrl: (url: string) => void;
  onRemoveReferenceUrl: (index: number) => void;
  onGenerate: () => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function InputPanel({
  selectedTemplate,
  formValues,
  advancedOptions,
  referenceUrls,
  generationStatus,
  onSelectTemplate,
  onFormChange,
  onAdvancedChange,
  onAddReferenceUrl,
  onRemoveReferenceUrl,
  onGenerate,
}: InputPanelProps) {
  const isGenerating = generationStatus === "generating";
  const hasTemplate = selectedTemplate !== null;
  const hasRequiredFields =
    !!formValues.product_name?.trim() && !!formValues.key_message?.trim();
  const isGenerateDisabled = !hasTemplate || !hasRequiredFields || isGenerating;

  const showReferenceUpload =
    selectedTemplate !== null && IMAGE_TEMPLATES.includes(selectedTemplate);

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="flex flex-1 flex-col gap-6 p-4">
        {/* Template Selection */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Choose a format
          </h2>
          <TemplateSelector
            selectedTemplate={selectedTemplate}
            onSelect={onSelectTemplate}
          />
        </section>

        {/* Dynamic Form (visible only when template is selected) */}
        {hasTemplate && (
          <section>
            <DynamicForm
              selectedTemplate={selectedTemplate}
              formValues={formValues}
              onFormChange={onFormChange}
            />
          </section>
        )}

        {/* Reference Upload (visible only for image-based templates) */}
        {showReferenceUpload && (
          <section>
            <ReferenceUpload
              referenceUrls={referenceUrls}
              onAddUrl={onAddReferenceUrl}
              onRemoveUrl={onRemoveReferenceUrl}
            />
          </section>
        )}

        {/* Advanced Options */}
        <section>
          <AdvancedDrawer
            advancedOptions={advancedOptions}
            onOptionsChange={onAdvancedChange}
          />
        </section>
      </div>

      {/* Generate Button — sticky at bottom */}
      <div className="sticky bottom-0 border-t border-border bg-background p-4">
        <Button
          variant="default"
          size="lg"
          className="w-full"
          disabled={isGenerateDisabled}
          onClick={onGenerate}
          aria-busy={isGenerating}
        >
          {isGenerating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
