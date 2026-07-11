import type {
  EasyGenerationState,
  TemplateType,
  AdvancedOptions,
  Version,
  GenerationError,
} from "@/types/easyGeneration";
import {
  TEMPLATE_CONFIGS,
  INITIAL_EASY_GENERATION_STATE,
} from "@/types/easyGeneration";

// ─── Action Types ────────────────────────────────────────────────────────────

interface SelectTemplateAction {
  type: "SELECT_TEMPLATE";
  payload: TemplateType;
}

interface UpdateFormAction {
  type: "UPDATE_FORM";
  payload: Record<string, string>;
}

interface SetAdvancedOptionsAction {
  type: "SET_ADVANCED_OPTIONS";
  payload: Partial<AdvancedOptions>;
}

interface AddReferenceUrlAction {
  type: "ADD_REFERENCE_URL";
  payload: string;
}

interface RemoveReferenceUrlAction {
  type: "REMOVE_REFERENCE_URL";
  payload: number;
}

interface StartGenerationAction {
  type: "START_GENERATION";
  payload: number; // generationStartTime
}

interface GenerationProgressAction {
  type: "GENERATION_PROGRESS";
  payload: string; // statusText
}

interface GenerationCompleteAction {
  type: "GENERATION_COMPLETE";
}

interface GenerationFailedAction {
  type: "GENERATION_FAILED";
  payload: GenerationError;
}

interface AddVersionAction {
  type: "ADD_VERSION";
  payload: Version;
}

interface SetActiveVersionAction {
  type: "SET_ACTIVE_VERSION";
  payload: string; // versionId
}

interface SetComparisonVersionAction {
  type: "SET_COMPARISON_VERSION";
  payload: string; // versionId chosen via "Use this"
}

interface ClearErrorAction {
  type: "CLEAR_ERROR";
}

interface ResetFormAction {
  type: "RESET_FORM";
}

export type EasyGenerationAction =
  | SelectTemplateAction
  | UpdateFormAction
  | SetAdvancedOptionsAction
  | AddReferenceUrlAction
  | RemoveReferenceUrlAction
  | StartGenerationAction
  | GenerationProgressAction
  | GenerationCompleteAction
  | GenerationFailedAction
  | AddVersionAction
  | SetActiveVersionAction
  | SetComparisonVersionAction
  | ClearErrorAction
  | ResetFormAction;

// ─── Helper ──────────────────────────────────────────────────────────────────

/**
 * Returns the set of allowed field keys for a given template type.
 */
function getAllowedFields(template: TemplateType): Set<string> {
  const config = TEMPLATE_CONFIGS[template];
  return new Set([...config.fields.common, ...config.fields.specific]);
}

/**
 * Filters formValues to only include fields that belong to the given template.
 * Property 3: Generation request excludes hidden fields from previous template.
 */
function filterFormValues(
  formValues: Record<string, string>,
  template: TemplateType
): Record<string, string> {
  const allowed = getAllowedFields(template);
  const filtered: Record<string, string> = {};
  for (const key of Object.keys(formValues)) {
    if (allowed.has(key)) {
      filtered[key] = formValues[key];
    }
  }
  return filtered;
}

// ─── Reducer ─────────────────────────────────────────────────────────────────

/**
 * Reducer for Easy Generation workspace state.
 *
 * Key invariants:
 * - SELECT_TEMPLATE clears fields not in new template schema (Property 3)
 * - GENERATION_FAILED preserves formValues, advancedOptions, referenceUrls, versions (Property 12)
 * - ADD_VERSION monotonically increases version count (Property 5)
 * - UPDATE_FORM does not merge revision instructions into form values (Property 6)
 *
 * Requirements: 2.2, 8.1, 9.2, 9.4, 16.1
 */
export function easyGenerationReducer(
  state: EasyGenerationState,
  action: EasyGenerationAction
): EasyGenerationState {
  switch (action.type) {
    case "SELECT_TEMPLATE": {
      const newTemplate = action.payload;
      // Property 3: clear fields that are not in the new template's schema
      const filteredFormValues = filterFormValues(state.formValues, newTemplate);
      return {
        ...state,
        selectedTemplate: newTemplate,
        formValues: filteredFormValues,
        generationStatus: "idle",
      };
    }

    case "UPDATE_FORM": {
      // Partial update — merge new field values into existing formValues
      return {
        ...state,
        formValues: { ...state.formValues, ...action.payload },
      };
    }

    case "SET_ADVANCED_OPTIONS": {
      // Partial update to advancedOptions
      return {
        ...state,
        advancedOptions: { ...state.advancedOptions, ...action.payload },
      };
    }

    case "ADD_REFERENCE_URL": {
      return {
        ...state,
        referenceUrls: [...state.referenceUrls, action.payload],
      };
    }

    case "REMOVE_REFERENCE_URL": {
      const index = action.payload;
      return {
        ...state,
        referenceUrls: state.referenceUrls.filter((_, i) => i !== index),
      };
    }

    case "START_GENERATION": {
      return {
        ...state,
        generationStatus: "generating",
        generationStartTime: action.payload,
        statusText: "",
        error: null,
      };
    }

    case "GENERATION_PROGRESS": {
      return {
        ...state,
        statusText: action.payload,
      };
    }

    case "GENERATION_COMPLETE": {
      return {
        ...state,
        generationStatus: "completed",
        error: null,
      };
    }

    case "GENERATION_FAILED": {
      // Property 12: Failure preserves form state and existing versions.
      // Only generationStatus and error change — formValues, advancedOptions,
      // referenceUrls, and versions remain untouched.
      return {
        ...state,
        generationStatus: "failed",
        error: action.payload,
      };
    }

    case "ADD_VERSION": {
      // Property 5: Version count monotonically increases.
      // If there was a previous activeVersionId, set it as comparisonVersionId
      // for side-by-side comparison (Requirement 8.1).
      const previousActiveId = state.activeVersionId;
      return {
        ...state,
        versions: [...state.versions, action.payload],
        activeVersionId: action.payload.id,
        comparisonVersionId: previousActiveId,
      };
    }

    case "SET_ACTIVE_VERSION": {
      // Sets activeVersionId and clears comparison mode
      return {
        ...state,
        activeVersionId: action.payload,
        comparisonVersionId: null,
      };
    }

    case "SET_COMPARISON_VERSION": {
      // "Use this" — sets the chosen version as active,
      // clears comparison mode (moves the other to history)
      // Property 14: Version selection in comparison mode
      return {
        ...state,
        activeVersionId: action.payload,
        comparisonVersionId: null,
      };
    }

    case "CLEAR_ERROR": {
      return {
        ...state,
        error: null,
        generationStatus: "idle",
      };
    }

    case "RESET_FORM": {
      return INITIAL_EASY_GENERATION_STATE;
    }

    default:
      return state;
  }
}
