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
  generationMode?: "easy" | "advanced";
  onToggleMode?: (mode: "easy" | "advanced") => void;
  autofillPrompt?: string;
  setAutofillPrompt?: (prompt: string) => void;
  isAutofilling?: boolean;
  onAutofill?: () => void;
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
  generationMode = "easy",
  onToggleMode,
  autofillPrompt = "",
  setAutofillPrompt,
  isAutofilling = false,
  onAutofill,
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
        {/* Mode Toggle Tabs */}
        {onToggleMode && (
          <div className="flex rounded-lg bg-surface-inset p-1 border border-border-default">
            <button
              onClick={() => onToggleMode("easy")}
              className={`flex-1 text-center py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                generationMode === "easy"
                  ? "bg-surface-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Easy Mode
            </button>
            <button
              onClick={() => onToggleMode("advanced")}
              className={`flex-1 text-center py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                generationMode === "advanced"
                  ? "bg-surface-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Advanced Mode
            </button>
          </div>
        )}

        {/* AI Form Filler Agent */}
        {onAutofill && setAutofillPrompt && (
          <section className="bg-surface-card border border-border-default rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-accent-blue uppercase">
              <Sparkles size={14} className="text-accent-blue" />
              AI Form Filler Agent
            </div>
            <p className="text-[11px] text-text-caption">
              Type your ad requirement in natural language, and let the AI fill out the form fields.
            </p>
            <textarea
              placeholder="e.g. Minimalist Instagram poster for green tea targeting millennials in Malaysia"
              value={autofillPrompt}
              onChange={(e) => setAutofillPrompt(e.target.value)}
              rows={2}
              className="w-full text-xs rounded-lg border border-border-default bg-surface-inset p-2 placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent-blue/30 resize-none"
            />
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs h-8"
              disabled={!autofillPrompt?.trim() || isAutofilling}
              onClick={onAutofill}
            >
              {isAutofilling ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin mr-1.5" />
                  Analyzing requirements...
                </>
              ) : (
                <>
                  <Sparkles className="h-3 w-3 mr-1.5 text-accent-blue" />
                  Auto-fill Form Fields
                </>
              )}
            </Button>
          </section>
        )}

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
