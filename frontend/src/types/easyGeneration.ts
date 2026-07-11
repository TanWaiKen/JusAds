/**
 * Shared TypeScript interfaces for the Easy Generation workspace.
 * These types define the template system, generation state, versioning,
 * and request/response shapes for the streamlined generation flow.
 */

// ─── Template Types ──────────────────────────────────────────────────────────

/**
 * Supported ad format categories for Easy Mode generation.
 */
export type TemplateType = "poster" | "story" | "carousel" | "text_copy";

/**
 * Configuration for a single template type, including its field schema,
 * aspect ratio, and media type mapping.
 */
export interface TemplateConfig {
  id: TemplateType;
  label: string;
  description: string;
  icon: string;
  aspectRatio: string;
  mediaType: "image" | "text";
  fields: {
    common: string[];
    specific: string[];
  };
}

// ─── Advanced Options ────────────────────────────────────────────────────────

/**
 * User-configurable advanced generation options exposed via the
 * "Need more control?" drawer.
 */
export interface AdvancedOptions {
  quality: "standard" | "high";
  styleStrength: "low" | "medium" | "high";
  keepLayout: boolean;
  extraInstructions: string;
}

// ─── Version Management ──────────────────────────────────────────────────────

/**
 * A single generated output tied to a project and task,
 * labeled sequentially (V1, V2, V3...).
 */
export interface Version {
  id: string;
  label: string;
  templateType: TemplateType;
  publicUrl: string | null;
  caption: string | null;
  revisionNote: string;
  timestamp: number;
  generationDuration: number;
  platform: string;
  dimensions: string;
}

// ─── Error Handling ──────────────────────────────────────────────────────────

/**
 * Generation error with retryability indicator for the UI recovery flow.
 */
export interface GenerationError {
  message: string;
  retryable: boolean;
}

// ─── State Management ────────────────────────────────────────────────────────

/**
 * Complete workspace state for the Easy Generation page,
 * managed via useReducer.
 */
export interface EasyGenerationState {
  selectedTemplate: TemplateType | null;
  formValues: Record<string, string>;
  advancedOptions: AdvancedOptions;
  referenceUrls: string[];

  generationStatus: "idle" | "generating" | "completed" | "failed";
  statusText: string;
  generationStartTime: number | null;

  versions: Version[];
  activeVersionId: string | null;
  comparisonVersionId: string | null;

  error: GenerationError | null;
}

// ─── API Request ─────────────────────────────────────────────────────────────

/**
 * Request payload sent to the existing chat endpoint in Easy Mode.
 * Maps frontend form state to the backend generation contract.
 */
export interface EasyGenerationRequest {
  message: string;
  guided_mode: true;
  design_type: string;
  guided_inputs: Record<string, string>;
  reference_urls: string[];
  target_platform: string;
  product_name: string;
  age_group: string;
  market: string;
  target_ethnicity: string;
  revision_instruction?: string;
  advanced_overrides?: AdvancedOptions;
}

// ─── Template Configuration Constant ─────────────────────────────────────────

/**
 * Static template configuration mapping each template type to its
 * field schema, aspect ratio, and media type. Derived from the backend
 * FORM_SCHEMA and used to drive dynamic form rendering.
 */
export const TEMPLATE_CONFIGS: Record<TemplateType, TemplateConfig> = {
  poster: {
    id: "poster",
    label: "Poster",
    description: "Single high-impact visual (1:1)",
    icon: "image",
    aspectRatio: "1:1",
    mediaType: "image",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["visual_style", "color_palette"],
    },
  },
  story: {
    id: "story",
    label: "Story",
    description: "Vertical visual for stories (9:16)",
    icon: "smartphone",
    aspectRatio: "9:16",
    mediaType: "image",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["visual_style", "color_palette"],
    },
  },
  carousel: {
    id: "carousel",
    label: "Carousel",
    description: "Multi-slide swipeable narrative",
    icon: "gallery-horizontal-end",
    aspectRatio: "1:1",
    mediaType: "image",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["visual_style", "color_palette", "slide_count"],
    },
  },
  text_copy: {
    id: "text_copy",
    label: "Text Copy",
    description: "Platform-optimized ad copy",
    icon: "type",
    aspectRatio: "text",
    mediaType: "text",
    fields: {
      common: ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
      specific: ["copy_length", "call_to_action", "language"],
    },
  },
};

// ─── Default State ───────────────────────────────────────────────────────────

/**
 * Default advanced options used when the drawer has not been modified.
 */
export const DEFAULT_ADVANCED_OPTIONS: AdvancedOptions = {
  quality: "standard",
  styleStrength: "medium",
  keepLayout: false,
  extraInstructions: "",
};

/**
 * Initial state for the Easy Generation reducer.
 */
export const INITIAL_EASY_GENERATION_STATE: EasyGenerationState = {
  selectedTemplate: null,
  formValues: {},
  advancedOptions: DEFAULT_ADVANCED_OPTIONS,
  referenceUrls: [],

  generationStatus: "idle",
  statusText: "",
  generationStartTime: null,

  versions: [],
  activeVersionId: null,
  comparisonVersionId: null,

  error: null,
};
