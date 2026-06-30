/**
 * Shared types for the Project Records page components.
 * Defines strict interfaces for task execution data, filters, and stats.
 */

export type TaskType = "generation" | "compliance" | "remix";
export type TaskStatus = "completed" | "failed" | "processing";
export type MediaType = "video" | "image" | "audio" | "text";

export interface TaskExecution {
  id: string;
  realId: string;
  type: TaskType;
  mediaType: MediaType;
  status: TaskStatus;
  tags: string[];
  date: string;
}

export interface ProjectStats {
  totalTasks: number;
  totalTasksDelta: string;
  successfulGenerations: number;
  successfulGenerationsLabel: string;
  compliancePasses: number;
  compliancePassRate: string;
}

export interface TaskFilters {
  type: TaskType | "all";
  status: TaskStatus | "all";
  search: string;
}
