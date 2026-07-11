/**
 * EasyGenerationPage — Single-page workspace for streamlined ad generation.
 *
 * Composes InputPanel, PreviewPanel, and FeedbackSidebar in a responsive
 * three-column layout. Manages all state via useReducer, handles SSE streaming
 * to the backend chat endpoint, and supports page-reload recovery via
 * getGeneratedAds().
 *
 * Requirements: 1.1, 1.2, 1.3, 1.4, 13.1, 13.2, 13.3, 13.4, 14.1, 14.2, 14.3, 14.4
 */

import { useReducer, useRef, useEffect, useState, useCallback, createContext, useContext } from "react";
import { useParams } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { PanelRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { InputPanel } from "@/components/easy-generation/InputPanel";
import { PreviewPanel } from "@/components/easy-generation/PreviewPanel";
import { FeedbackSidebar } from "@/components/easy-generation/FeedbackSidebar";
import { easyGenerationReducer } from "@/reducers/easyGenerationReducer";
import {
  INITIAL_EASY_GENERATION_STATE,
  TEMPLATE_CONFIGS,
} from "@/types/easyGeneration";
import type {
  EasyGenerationState,
  TemplateType,
  AdvancedOptions,
  Version,
  EasyGenerationRequest,
} from "@/types/easyGeneration";
import type { EasyGenerationAction } from "@/reducers/easyGenerationReducer";
import {
  API_BASE,
  parseSSEStream,
  getGeneratedAds,
} from "@/services/generationApi";
import { createGenerationTask } from "@/services/taskApi";

gsap.registerPlugin(useGSAP);

// ─── Context ─────────────────────────────────────────────────────────────────

interface EasyGenerationContextValue {
  state: EasyGenerationState;
  dispatch: React.Dispatch<EasyGenerationAction>;
}

const EasyGenerationContext = createContext<EasyGenerationContextValue | null>(null);

export function useEasyGeneration(): EasyGenerationContextValue {
  const ctx = useContext(EasyGenerationContext);
  if (!ctx) throw new Error("useEasyGeneration must be used within EasyGenerationPage");
  return ctx;
}

// ─── Template → Backend Mapping ──────────────────────────────────────────────

function getDesignType(template: TemplateType): string {
  switch (template) {
    case "poster":
      return "image_poster";
    case "story":
      return "image_poster";
    case "carousel":
      return "carousel";
    case "text_copy":
      return "text_copy";
  }
}

function getForceMediaTypes(template: TemplateType): string[] {
  switch (template) {
    case "poster":
    case "story":
    case "carousel":
      return ["image"];
    case "text_copy":
      return ["text"];
  }
}

function getDimensions(template: TemplateType): string {
  switch (template) {
    case "poster":
      return "1080×1080";
    case "story":
      return "1080×1920";
    case "carousel":
      return "1080×1080";
    case "text_copy":
      return "N/A";
  }
}

// ─── SSE Event Interfaces ────────────────────────────────────────────────────

interface SSENodeEvent {
  node?: string;
  status?: "in-progress" | "completed" | "failed";
  data?: { message?: string; phase?: string };
}

interface SSEPipelineEvent {
  pipeline_state?: {
    generated_ads?: Array<{
      ad_id?: string;
      gen_status?: string;
      public_url?: string;
      caption?: string;
      platform?: string;
      media_type?: string;
    }>;
  };
}

interface SSEErrorEvent {
  error?: string;
}

// ─── Component ───────────────────────────────────────────────────────────────

function EasyGenerationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [state, dispatch] = useReducer(easyGenerationReducer, INITIAL_EASY_GENERATION_STATE);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastRevisionRef = useRef<string>("");
  const lastRequestRef = useRef<EasyGenerationRequest | null>(null);
  const inputPanelRef = useRef<HTMLDivElement>(null);
  const previewPanelRef = useRef<HTMLDivElement>(null);

  // ─── GSAP page entrance animation ───────────────────────────────────────

  useGSAP(
    () => {
      gsap.from(".easy-gen-panel", {
        y: 20,
        autoAlpha: 0,
        stagger: 0.1,
        duration: 0.5,
        ease: "power2.out",
      });
    },
    { scope: containerRef }
  );

  // ─── Initialize task and load existing versions on mount ────────────────

  useEffect(() => {
    if (!projectId) return;

    async function initialize() {
      try {
        // Create a new generation task for this Easy Mode session
        const task = await createGenerationTask(projectId!);
        setTaskId(task.id);

        // Try to load existing generated ads (page reload recovery)
        const existingAds = await getGeneratedAds(projectId!, task.id);
        if (existingAds.length > 0) {
          for (let i = 0; i < existingAds.length; i++) {
            const ad = existingAds[i];
            const version: Version = {
              id: ad.adId,
              label: `V${i + 1}`,
              templateType: (state.selectedTemplate as TemplateType) ?? "poster",
              publicUrl: ad.publicUrl,
              caption: ad.caption,
              revisionNote: i === 0 ? "Initial generation" : `Revision ${i}`,
              timestamp: Date.now() - (existingAds.length - i) * 1000,
              generationDuration: 0,
              platform: ad.platform,
              dimensions: getDimensions(state.selectedTemplate ?? "poster"),
            };
            dispatch({ type: "ADD_VERSION", payload: version });
          }
          if (existingAds.length > 0) {
            dispatch({ type: "GENERATION_COMPLETE" });
          }
        }
      } catch {
        // Task creation failed — continue with null taskId; will retry on generate
      }
    }

    initialize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ─── Build request payload ──────────────────────────────────────────────

  const buildRequest = useCallback(
    (revisionInstruction?: string): EasyGenerationRequest | null => {
      if (!state.selectedTemplate) return null;

      const template = state.selectedTemplate;
      const config = TEMPLATE_CONFIGS[template];
      const allowedFields = new Set([...config.fields.common, ...config.fields.specific]);

      // Filter form values to only visible fields (Property 3)
      const guidedInputs: Record<string, string> = {};
      for (const [key, value] of Object.entries(state.formValues)) {
        if (allowedFields.has(key) && value.trim()) {
          guidedInputs[key] = value;
        }
      }

      const request: EasyGenerationRequest = {
        message: `Generate ${config.label} for ${state.formValues.product_name || "product"}`,
        guided_mode: true,
        design_type: getDesignType(template),
        guided_inputs: guidedInputs,
        reference_urls: state.referenceUrls,
        target_platform: state.formValues.platform || "instagram",
        product_name: state.formValues.product_name || "",
        age_group: state.formValues.age_group || "all_ages",
        market: state.formValues.market || "malaysia",
        target_ethnicity: state.formValues.target_ethnicity || "all",
      };

      // Include revision instruction (Property 6 & 7 — stored separately)
      if (revisionInstruction) {
        request.revision_instruction = revisionInstruction;
      }

      // Include advanced overrides if modified
      const defaults = INITIAL_EASY_GENERATION_STATE.advancedOptions;
      const current = state.advancedOptions;
      if (
        current.quality !== defaults.quality ||
        current.styleStrength !== defaults.styleStrength ||
        current.keepLayout !== defaults.keepLayout ||
        current.extraInstructions.trim() !== ""
      ) {
        request.advanced_overrides = current;
      }

      return request;
    },
    [state.selectedTemplate, state.formValues, state.referenceUrls, state.advancedOptions]
  );

  // ─── SSE Streaming ─────────────────────────────────────────────────────

  const startGeneration = useCallback(
    async (revisionInstruction?: string) => {
      if (!projectId) return;

      let currentTaskId = taskId;

      // Ensure we have a task
      if (!currentTaskId) {
        try {
          const task = await createGenerationTask(projectId);
          setTaskId(task.id);
          currentTaskId = task.id;
        } catch {
          dispatch({
            type: "GENERATION_FAILED",
            payload: { message: "Failed to create generation task. Please try again.", retryable: true },
          });
          return;
        }
      }

      const request = buildRequest(revisionInstruction);
      if (!request) return;

      // Property 13: Store request so Retry can re-submit identical payload
      lastRequestRef.current = request;

      // Store revision instruction for version labeling
      lastRevisionRef.current = revisionInstruction || "";

      // Dispatch START_GENERATION
      const startTime = Date.now();
      dispatch({ type: "START_GENERATION", payload: startTime });

      // Abort any previous stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${projectId}/tasks/${currentTaskId}/chat`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...request,
              force_media_types: getForceMediaTypes(state.selectedTemplate!),
            }),
            signal: abortController.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`Generation failed: ${response.status} ${response.statusText}`);
        }

        // Parse SSE stream
        for await (const event of parseSSEStream(response)) {
          if (abortController.signal.aborted) break;

          const sseEvent = event as SSENodeEvent & SSEPipelineEvent & SSEErrorEvent;

          // Handle error events
          if (sseEvent.error) {
            dispatch({
              type: "GENERATION_FAILED",
              payload: { message: sseEvent.error, retryable: true },
            });
            return;
          }

          // Handle node progress events
          if (sseEvent.node && sseEvent.status === "in-progress" && sseEvent.data) {
            const message = sseEvent.data.message || sseEvent.data.phase || "Generating...";
            dispatch({ type: "GENERATION_PROGRESS", payload: message });
          }

          // Handle pipeline_state events — extract generated_ads
          if (sseEvent.pipeline_state) {
            const generatedAds = sseEvent.pipeline_state.generated_ads;
            if (Array.isArray(generatedAds)) {
              for (const ad of generatedAds) {
                if (ad.gen_status === "completed" || ad.public_url || ad.caption) {
                  const version: Version = {
                    id: ad.ad_id || `ad-${Date.now()}`,
                    label: `V${state.versions.length + 1}`,
                    templateType: state.selectedTemplate!,
                    publicUrl: ad.public_url ?? null,
                    caption: ad.caption ?? null,
                    revisionNote: lastRevisionRef.current || "Initial generation",
                    timestamp: Date.now(),
                    generationDuration: Date.now() - startTime,
                    platform: ad.platform || state.formValues.platform || "instagram",
                    dimensions: getDimensions(state.selectedTemplate!),
                  };
                  dispatch({ type: "ADD_VERSION", payload: version });
                }
              }
              dispatch({ type: "GENERATION_COMPLETE" });
              // Focus management: move focus to preview on completion (Req 15.3)
              requestAnimationFrame(() => {
                previewPanelRef.current?.focus();
              });
            }
          }

          // Handle completed node events (check if it contains ad data)
          if (sseEvent.node && sseEvent.status === "completed" && sseEvent.data) {
            const data = sseEvent.data as Record<string, unknown>;
            if (data.message && typeof data.message === "string") {
              dispatch({ type: "GENERATION_PROGRESS", payload: data.message });
            }
          }
        }

        // If stream ended without pipeline_state, check for completion
        // (SSE disconnect fallback — Req 16, Design Error Handling)
        if (state.generationStatus === "generating") {
          try {
            const ads = await getGeneratedAds(projectId, currentTaskId);
            if (ads.length > state.versions.length) {
              const newAds = ads.slice(state.versions.length);
              for (let i = 0; i < newAds.length; i++) {
                const ad = newAds[i];
                const version: Version = {
                  id: ad.adId,
                  label: `V${state.versions.length + i + 1}`,
                  templateType: state.selectedTemplate!,
                  publicUrl: ad.publicUrl,
                  caption: ad.caption,
                  revisionNote: lastRevisionRef.current || "Initial generation",
                  timestamp: Date.now(),
                  generationDuration: Date.now() - startTime,
                  platform: ad.platform || "instagram",
                  dimensions: getDimensions(state.selectedTemplate!),
                };
                dispatch({ type: "ADD_VERSION", payload: version });
              }
              dispatch({ type: "GENERATION_COMPLETE" });
              // Focus management: move focus to preview on completion (Req 15.3)
              requestAnimationFrame(() => {
                previewPanelRef.current?.focus();
              });
            }
          } catch {
            // Fallback fetch also failed — mark as error
            dispatch({
              type: "GENERATION_FAILED",
              payload: { message: "Connection lost during generation. Please retry.", retryable: true },
            });
          }
        }
      } catch (err) {
        if (abortController.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Generation failed. Please try again.";
        dispatch({
          type: "GENERATION_FAILED",
          payload: { message, retryable: true },
        });
      }
    },
    [projectId, taskId, buildRequest, state.selectedTemplate, state.formValues, state.versions.length, state.generationStatus]
  );

  // ─── Cleanup on unmount ─────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ─── Event Handlers ─────────────────────────────────────────────────────

  const handleSelectTemplate = useCallback((template: TemplateType) => {
    dispatch({ type: "SELECT_TEMPLATE", payload: template });
  }, []);

  const handleFormChange = useCallback((values: Record<string, string>) => {
    dispatch({ type: "UPDATE_FORM", payload: values });
  }, []);

  const handleAdvancedChange = useCallback((options: Partial<AdvancedOptions>) => {
    dispatch({ type: "SET_ADVANCED_OPTIONS", payload: options });
  }, []);

  const handleAddReferenceUrl = useCallback((url: string) => {
    dispatch({ type: "ADD_REFERENCE_URL", payload: url });
  }, []);

  const handleRemoveReferenceUrl = useCallback((index: number) => {
    dispatch({ type: "REMOVE_REFERENCE_URL", payload: index });
  }, []);

  const handleGenerate = useCallback(() => {
    startGeneration();
  }, [startGeneration]);

  const handleSubmitRevision = useCallback(
    (instruction: string) => {
      // Property 6: Revision instruction stored separately — NOT in formValues
      startGeneration(instruction);
    },
    [startGeneration]
  );

  const handleSelectVersion = useCallback((versionId: string) => {
    dispatch({ type: "SET_ACTIVE_VERSION", payload: versionId });
  }, []);

  // ─── Error Recovery Handlers (Req 16.2, 16.3, 16.4) ────────────────────

  /**
   * Retry: re-submit the exact same request payload (Property 13).
   */
  const handleRetry = useCallback(() => {
    if (!lastRequestRef.current || !projectId) return;

    const request = lastRequestRef.current;
    // Re-use the stored request directly so it's identical
    const retryGeneration = async () => {
      let currentTaskId = taskId;
      if (!currentTaskId) {
        try {
          const task = await createGenerationTask(projectId);
          setTaskId(task.id);
          currentTaskId = task.id;
        } catch {
          dispatch({
            type: "GENERATION_FAILED",
            payload: { message: "Failed to create generation task. Please try again.", retryable: true },
          });
          return;
        }
      }

      const startTime = Date.now();
      dispatch({ type: "START_GENERATION", payload: startTime });

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const response = await fetch(
          `${API_BASE}/api/projects/${projectId}/tasks/${currentTaskId}/chat`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              ...request,
              force_media_types: state.selectedTemplate
                ? getForceMediaTypes(state.selectedTemplate)
                : ["image"],
            }),
            signal: abortController.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`Generation failed: ${response.status} ${response.statusText}`);
        }

        for await (const event of parseSSEStream(response)) {
          if (abortController.signal.aborted) break;

          const sseEvent = event as SSENodeEvent & SSEPipelineEvent & SSEErrorEvent;

          if (sseEvent.error) {
            dispatch({
              type: "GENERATION_FAILED",
              payload: { message: sseEvent.error, retryable: true },
            });
            return;
          }

          if (sseEvent.node && sseEvent.status === "in-progress" && sseEvent.data) {
            const message = sseEvent.data.message || sseEvent.data.phase || "Generating...";
            dispatch({ type: "GENERATION_PROGRESS", payload: message });
          }

          if (sseEvent.pipeline_state) {
            const generatedAds = sseEvent.pipeline_state.generated_ads;
            if (Array.isArray(generatedAds)) {
              for (const ad of generatedAds) {
                if (ad.gen_status === "completed" || ad.public_url || ad.caption) {
                  const version: Version = {
                    id: ad.ad_id || `ad-${Date.now()}`,
                    label: `V${state.versions.length + 1}`,
                    templateType: state.selectedTemplate!,
                    publicUrl: ad.public_url ?? null,
                    caption: ad.caption ?? null,
                    revisionNote: lastRevisionRef.current || "Initial generation",
                    timestamp: Date.now(),
                    generationDuration: Date.now() - startTime,
                    platform: ad.platform || state.formValues.platform || "instagram",
                    dimensions: getDimensions(state.selectedTemplate!),
                  };
                  dispatch({ type: "ADD_VERSION", payload: version });
                }
              }
              dispatch({ type: "GENERATION_COMPLETE" });
              requestAnimationFrame(() => {
                previewPanelRef.current?.focus();
              });
            }
          }
        }

        // SSE disconnect fallback
        if (state.generationStatus === "generating") {
          try {
            const ads = await getGeneratedAds(projectId, currentTaskId);
            if (ads.length > state.versions.length) {
              const newAds = ads.slice(state.versions.length);
              for (let i = 0; i < newAds.length; i++) {
                const ad = newAds[i];
                const version: Version = {
                  id: ad.adId,
                  label: `V${state.versions.length + i + 1}`,
                  templateType: state.selectedTemplate!,
                  publicUrl: ad.publicUrl,
                  caption: ad.caption,
                  revisionNote: lastRevisionRef.current || "Initial generation",
                  timestamp: Date.now(),
                  generationDuration: Date.now() - startTime,
                  platform: ad.platform || "instagram",
                  dimensions: getDimensions(state.selectedTemplate!),
                };
                dispatch({ type: "ADD_VERSION", payload: version });
              }
              dispatch({ type: "GENERATION_COMPLETE" });
              requestAnimationFrame(() => {
                previewPanelRef.current?.focus();
              });
            }
          } catch {
            dispatch({
              type: "GENERATION_FAILED",
              payload: { message: "Connection lost during generation. Please retry.", retryable: true },
            });
          }
        }
      } catch (err) {
        if (abortController.signal.aborted) return;
        const message = err instanceof Error ? err.message : "Generation failed. Please try again.";
        dispatch({
          type: "GENERATION_FAILED",
          payload: { message, retryable: true },
        });
      }
    };

    retryGeneration();
  }, [projectId, taskId, state.selectedTemplate, state.formValues, state.versions.length, state.generationStatus]);

  /**
   * Edit Inputs: return focus to InputPanel with values intact (Req 16.4).
   * Clears the error and scrolls/focuses the input panel.
   */
  const handleEditInputs = useCallback(() => {
    dispatch({ type: "CLEAR_ERROR" });
    requestAnimationFrame(() => {
      inputPanelRef.current?.focus();
      inputPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  /**
   * Dismiss: clears error, returns to idle state.
   */
  const handleDismissError = useCallback(() => {
    dispatch({ type: "CLEAR_ERROR" });
  }, []);

  // ─── Derived State ──────────────────────────────────────────────────────

  const activeVersion = state.versions.find((v) => v.id === state.activeVersionId) ?? null;
  const comparisonVersion = state.versions.find((v) => v.id === state.comparisonVersionId) ?? null;

  // ─── Sidebar Content (reused in sheet and inline) ───────────────────────

  const sidebarContent = (
    <FeedbackSidebar
      activeVersion={activeVersion}
      versions={state.versions}
      activeVersionId={state.activeVersionId}
      generationStatus={state.generationStatus}
      onSubmitRevision={handleSubmitRevision}
      onSelectVersion={handleSelectVersion}
    />
  );

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <EasyGenerationContext.Provider value={{ state, dispatch }}>
      <div ref={containerRef} className="flex h-full flex-col overflow-hidden">
        {/* Desktop layout: 3-column grid (≥1024px) */}
        <div className="hidden h-full lg:grid lg:grid-cols-[320px_1fr_280px]">
          {/* Input Panel */}
          <div ref={inputPanelRef} tabIndex={-1} className="easy-gen-panel border-r border-border outline-none">
            <InputPanel
              selectedTemplate={state.selectedTemplate}
              formValues={state.formValues}
              advancedOptions={state.advancedOptions}
              referenceUrls={state.referenceUrls}
              generationStatus={state.generationStatus}
              onSelectTemplate={handleSelectTemplate}
              onFormChange={handleFormChange}
              onAdvancedChange={handleAdvancedChange}
              onAddReferenceUrl={handleAddReferenceUrl}
              onRemoveReferenceUrl={handleRemoveReferenceUrl}
              onGenerate={handleGenerate}
            />
          </div>

          {/* Preview Panel */}
          <div ref={previewPanelRef} tabIndex={-1} className="easy-gen-panel outline-none">
            <PreviewPanel
              selectedTemplate={state.selectedTemplate}
              generationStatus={state.generationStatus}
              statusText={state.statusText}
              generationStartTime={state.generationStartTime}
              activeVersion={activeVersion}
              comparisonVersion={comparisonVersion}
              error={state.error}
              onSelectVersion={handleSelectVersion}
              onRetry={handleRetry}
              onEditInputs={handleEditInputs}
              onDismiss={handleDismissError}
            />
          </div>

          {/* Feedback Sidebar */}
          <div className="easy-gen-panel border-l border-border">
            {sidebarContent}
          </div>
        </div>

        {/* Tablet layout: 2-column grid + sidebar sheet (768–1023px) */}
        <div className="hidden h-full md:grid md:grid-cols-[300px_1fr] lg:hidden">
          {/* Input Panel */}
          <div className="easy-gen-panel border-r border-border">
            <InputPanel
              selectedTemplate={state.selectedTemplate}
              formValues={state.formValues}
              advancedOptions={state.advancedOptions}
              referenceUrls={state.referenceUrls}
              generationStatus={state.generationStatus}
              onSelectTemplate={handleSelectTemplate}
              onFormChange={handleFormChange}
              onAdvancedChange={handleAdvancedChange}
              onAddReferenceUrl={handleAddReferenceUrl}
              onRemoveReferenceUrl={handleRemoveReferenceUrl}
              onGenerate={handleGenerate}
            />
          </div>

          {/* Preview Panel */}
          <div className="easy-gen-panel relative">
            <PreviewPanel
              selectedTemplate={state.selectedTemplate}
              generationStatus={state.generationStatus}
              statusText={state.statusText}
              generationStartTime={state.generationStartTime}
              activeVersion={activeVersion}
              comparisonVersion={comparisonVersion}
              error={state.error}
              onSelectVersion={handleSelectVersion}
              onRetry={handleRetry}
              onEditInputs={handleEditInputs}
              onDismiss={handleDismissError}
            />

            {/* Sidebar toggle button */}
            <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
              <SheetTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon"
                    className="absolute right-4 top-4 z-10"
                    aria-label="Open feedback sidebar"
                  />
                }
              >
                <PanelRight className="h-4 w-4" />
              </SheetTrigger>
              <SheetContent side="right" className="w-[300px] p-0">
                <SheetHeader className="border-b border-border">
                  <SheetTitle>Feedback & Versions</SheetTitle>
                </SheetHeader>
                {sidebarContent}
              </SheetContent>
            </Sheet>
          </div>
        </div>

        {/* Mobile layout: stacked (< 768px) */}
        <div className="flex h-full flex-col overflow-y-auto md:hidden">
          {/* Input Panel */}
          <div className="easy-gen-panel border-b border-border">
            <InputPanel
              selectedTemplate={state.selectedTemplate}
              formValues={state.formValues}
              advancedOptions={state.advancedOptions}
              referenceUrls={state.referenceUrls}
              generationStatus={state.generationStatus}
              onSelectTemplate={handleSelectTemplate}
              onFormChange={handleFormChange}
              onAdvancedChange={handleAdvancedChange}
              onAddReferenceUrl={handleAddReferenceUrl}
              onRemoveReferenceUrl={handleRemoveReferenceUrl}
              onGenerate={handleGenerate}
            />
          </div>

          {/* Preview Panel */}
          <div className="easy-gen-panel min-h-[300px]">
            <PreviewPanel
              selectedTemplate={state.selectedTemplate}
              generationStatus={state.generationStatus}
              statusText={state.statusText}
              generationStartTime={state.generationStartTime}
              activeVersion={activeVersion}
              comparisonVersion={comparisonVersion}
              error={state.error}
              onSelectVersion={handleSelectVersion}
              onRetry={handleRetry}
              onEditInputs={handleEditInputs}
              onDismiss={handleDismissError}
            />
          </div>

          {/* Feedback Sidebar */}
          <div className="easy-gen-panel border-t border-border">
            {sidebarContent}
          </div>
        </div>
      </div>
    </EasyGenerationContext.Provider>
  );
}

export default EasyGenerationPage;
