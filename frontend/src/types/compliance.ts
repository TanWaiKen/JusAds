/**
 * Shared TypeScript interfaces for compliance queue state management.
 * These types are used across compliance components for the review queue,
 * upload form, error handling, and the project-based workflow.
 */

import type { ComplianceResult } from "@/services/complianceApi";

export interface ViolationFlag {
  category: string;
  color: "error" | "ship-red" | "amber";
}

export type RiskLevel = "High" | "Medium" | "Low";

export interface QueueItem {
  id: string;
  campaignName: string;
  assetFilename: string;
  mediaType: "video" | "image" | "audio" | "text";
  platform: string[];
  riskLevel: RiskLevel | null;
  flags: ViolationFlag[];
  status: "passed" | "needs_changes" | "in_progress" | "error";
  lastChecked: Date;
  thumbnailUrl?: string;
  result: ComplianceResult | null;
}

export interface UploadParams {
  file?: File;
  text?: string;
  market: string;
  ethnicity: string;
  ageGroup: string;
}

export type QueueAction =
  | { type: "ADD_ITEM"; payload: QueueItem }
  | { type: "UPDATE_STATUS"; id: string; status: QueueItem["status"] }
  | { type: "SET_RESULT"; id: string; result: ComplianceResult }
  | { type: "SET_ERROR"; id: string; error: string };

export interface ErrorState {
  type: "validation" | "connection" | "server" | "stream_incomplete";
  message: string;
  retryable: boolean;
}

// ─── Project-Based Workflow Types ─────────────────────────────────────────────

/**
 * The five workflow steps for a compliance project.
 */
export type WorkflowStep = "upload" | "check" | "review" | "remix" | "compare";

/**
 * Step definition for the StepNavigator component.
 */
export interface StepDefinition {
  id: WorkflowStep;
  label: string;
  icon: string; // Material Symbols icon name
}

/**
 * A compliance project representing a single check lifecycle.
 * Replaces QueueItem as the primary state unit.
 */
export interface Project {
  id: string;
  campaignName: string;
  mediaType: "video" | "image" | "audio" | "text";
  currentStep: WorkflowStep;
  completedSteps: WorkflowStep[];
  uploadParams: UploadParams;
  result: ComplianceResult | null;
  remixResult: unknown | null;
  error: ProjectError | null;
  createdAt: number;
}

/**
 * Error state scoped to a project and step.
 */
export interface ProjectError {
  step: WorkflowStep;
  message: string;
  retryable: boolean;
}

/**
 * Actions for the project store reducer.
 */
export type ProjectAction =
  | { type: "CREATE_PROJECT"; payload: Project }
  | { type: "SET_ACTIVE_PROJECT"; projectId: string }
  | { type: "ADVANCE_STEP"; projectId: string; to: WorkflowStep }
  | { type: "SET_RESULT"; projectId: string; result: ComplianceResult }
  | { type: "SET_REMIX_RESULT"; projectId: string; remixResult: unknown }
  | { type: "SET_ERROR"; projectId: string; error: ProjectError }
  | { type: "CLEAR_ERROR"; projectId: string }
  | { type: "NAVIGATE_TO_STEP"; projectId: string; step: WorkflowStep };

/**
 * The full project store state.
 */
export interface ProjectStore {
  projects: Map<string, Project>;
  activeProjectId: string | null;
}

/**
 * Ordered step definitions for the compliance workflow.
 */
export const WORKFLOW_STEPS: readonly StepDefinition[] = [
  { id: "upload", label: "Upload", icon: "upload_file" },
  { id: "check", label: "Check", icon: "verified_user" },
  { id: "review", label: "Review", icon: "rate_review" },
  { id: "remix", label: "Remix", icon: "auto_fix_high" },
  { id: "compare", label: "Compare", icon: "compare" },
] as const;
