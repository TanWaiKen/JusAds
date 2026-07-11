/**
 * Error Handling and Retry Flow Tests
 *
 * Tests the error display integration, retry logic (Property 13),
 * focus management, and SSE disconnect fallback behavior.
 *
 * **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 15.1, 15.3, 19.3**
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { easyGenerationReducer } from "@/reducers/easyGenerationReducer";
import {
  INITIAL_EASY_GENERATION_STATE,
} from "@/types/easyGeneration";
import type { EasyGenerationState, GenerationError, Version } from "@/types/easyGeneration";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const COMPONENTS_DIR = resolve(__dirname, "../components/easy-generation");
const PAGES_DIR = resolve(__dirname, "../pages");

function readComponent(filename: string): string {
  return readFileSync(resolve(COMPONENTS_DIR, filename), "utf-8");
}

function readPage(filename: string): string {
  return readFileSync(resolve(PAGES_DIR, filename), "utf-8");
}

function makeVersion(index: number): Version {
  return {
    id: `v-${index}`,
    label: `V${index}`,
    templateType: "poster",
    publicUrl: `https://example.com/image-${index}.png`,
    caption: null,
    revisionNote: index === 1 ? "Initial generation" : `Revision ${index - 1}`,
    timestamp: Date.now() - (10 - index) * 1000,
    generationDuration: 3000,
    platform: "instagram",
    dimensions: "1080×1080",
  };
}

// ─── Reducer: Error State Preservation (Property 12 / Req 16.1) ──────────────

describe("Error Handling - Reducer", () => {
  it("GENERATION_FAILED preserves form state and versions (Property 12)", () => {
    const stateWithData: EasyGenerationState = {
      ...INITIAL_EASY_GENERATION_STATE,
      selectedTemplate: "poster",
      formValues: { product_name: "Test Product", key_message: "Buy now" },
      advancedOptions: { quality: "high", styleStrength: "medium", keepLayout: false, extraInstructions: "" },
      referenceUrls: ["https://example.com/ref.png"],
      generationStatus: "generating",
      versions: [makeVersion(1)],
      activeVersionId: "v-1",
      comparisonVersionId: null,
      error: null,
      statusText: "Generating...",
      generationStartTime: Date.now(),
    };

    const error: GenerationError = { message: "Service unavailable", retryable: true };
    const result = easyGenerationReducer(stateWithData, {
      type: "GENERATION_FAILED",
      payload: error,
    });

    // Form state preserved
    expect(result.selectedTemplate).toBe("poster");
    expect(result.formValues).toEqual({ product_name: "Test Product", key_message: "Buy now" });
    expect(result.advancedOptions.quality).toBe("high");
    expect(result.referenceUrls).toEqual(["https://example.com/ref.png"]);

    // Versions preserved
    expect(result.versions).toHaveLength(1);
    expect(result.versions[0].id).toBe("v-1");

    // Error state set
    expect(result.generationStatus).toBe("failed");
    expect(result.error).toEqual(error);
  });

  it("CLEAR_ERROR resets to idle state", () => {
    const failedState: EasyGenerationState = {
      ...INITIAL_EASY_GENERATION_STATE,
      generationStatus: "failed",
      error: { message: "Something went wrong", retryable: true },
    };

    const result = easyGenerationReducer(failedState, { type: "CLEAR_ERROR" });

    expect(result.generationStatus).toBe("idle");
    expect(result.error).toBeNull();
  });
});

// ─── ErrorDisplay Component Structure ────────────────────────────────────────

describe("ErrorDisplay Component", () => {
  const source = readComponent("ErrorDisplay.tsx");

  it("exports a named ErrorDisplay component", () => {
    expect(source).toContain("export function ErrorDisplay");
  });

  it("uses alert role for accessibility", () => {
    expect(source).toContain('role="alert"');
  });

  it("uses aria-live assertive for error announcements", () => {
    expect(source).toContain('aria-live="assertive"');
  });

  it("auto-focuses the error container on mount (Req 15.3)", () => {
    expect(source).toContain("containerRef.current?.focus()");
  });

  it("renders Retry button calling onRetry", () => {
    expect(source).toContain("onRetry");
    expect(source).toContain("Retry");
    expect(source).toContain("RefreshCw");
  });

  it("renders Edit Inputs button calling onEditInputs", () => {
    expect(source).toContain("onEditInputs");
    expect(source).toContain("Edit Inputs");
    expect(source).toContain("PencilLine");
  });

  it("renders Dismiss button calling onDismiss", () => {
    expect(source).toContain("onDismiss");
    expect(source).toContain("Dismiss");
  });

  it("shows Retry button only when error is retryable", () => {
    expect(source).toContain("error.retryable");
  });

  it("uses destructive styling for error card", () => {
    expect(source).toContain("border-destructive");
    expect(source).toContain("text-destructive");
  });
});

// ─── PreviewPanel Error Integration ──────────────────────────────────────────

describe("PreviewPanel - Error Display Integration", () => {
  const source = readComponent("PreviewPanel.tsx");

  it("imports ErrorDisplay component", () => {
    expect(source).toContain('import { ErrorDisplay } from "@/components/easy-generation/ErrorDisplay"');
  });

  it("accepts error prop in its interface", () => {
    expect(source).toContain("error: GenerationError | null");
  });

  it("accepts onRetry, onEditInputs, onDismiss callback props", () => {
    expect(source).toContain("onRetry: () => void");
    expect(source).toContain("onEditInputs: () => void");
    expect(source).toContain("onDismiss: () => void");
  });

  it("renders ErrorDisplay when generationStatus is failed", () => {
    expect(source).toContain('generationStatus === "failed"');
    expect(source).toContain("<ErrorDisplay");
  });

  it("announces error state via aria-live region", () => {
    expect(source).toContain("generationStatus === \"failed\" && error");
  });
});

// ─── Page-Level Error Handling Logic ─────────────────────────────────────────

describe("EasyGenerationPage - Error and Retry Flow", () => {
  const source = readPage("easy-generation.tsx");

  it("stores lastRequest ref for retry (Property 13)", () => {
    expect(source).toContain("lastRequestRef");
    expect(source).toContain("lastRequestRef.current = request");
  });

  it("has handleRetry that re-uses lastRequestRef", () => {
    expect(source).toContain("handleRetry");
    expect(source).toContain("lastRequestRef.current");
  });

  it("has handleEditInputs that clears error and focuses InputPanel (Req 16.4)", () => {
    expect(source).toContain("handleEditInputs");
    expect(source).toContain("CLEAR_ERROR");
    expect(source).toContain("inputPanelRef.current?.focus()");
  });

  it("has handleDismissError that dispatches CLEAR_ERROR", () => {
    expect(source).toContain("handleDismissError");
    expect(source).toContain("CLEAR_ERROR");
  });

  it("handles SSE disconnect with getGeneratedAds fallback", () => {
    expect(source).toContain("getGeneratedAds");
    expect(source).toContain("Connection lost during generation");
  });

  it("moves focus to preview panel on generation completion (Req 15.3)", () => {
    expect(source).toContain("previewPanelRef.current?.focus()");
  });

  it("keeps form elements interactive during generation (Req 19.3)", () => {
    // The InputPanel only disables the Generate button — no fields are disabled during generation.
    // Verify the page does NOT add any disabled state to the InputPanel during generation.
    // The isGenerateDisabled logic in InputPanel only disables the Generate button.
    const inputPanelSource = readComponent("InputPanel.tsx");
    expect(inputPanelSource).toContain("isGenerating");
    expect(inputPanelSource).toContain("disabled={isGenerateDisabled}");
    // Form fields are never disabled based on generation status
    expect(inputPanelSource).not.toContain("disabled={isGenerating}");
  });

  it("passes error and error handlers to all PreviewPanel instances", () => {
    // Count occurrences of error prop being passed to PreviewPanel
    const errorPropMatches = source.match(/error=\{state\.error\}/g);
    expect(errorPropMatches).not.toBeNull();
    expect(errorPropMatches!.length).toBeGreaterThanOrEqual(3); // desktop, tablet, mobile
  });
});
