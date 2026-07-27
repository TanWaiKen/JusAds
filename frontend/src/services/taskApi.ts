/**
 * Task API Service
 * Connects to the project tasks backend at /api/projects/{projectId}/tasks
 */

import type { PipelineState } from "@/components/workspace/canvas/graphModel";
import { API_BASE } from "@/lib/apiConfig";
import { authenticatedFetch, toApiRequestError } from "@/lib/apiAuth";

export { API_BASE };

export interface ViolationSummary {
  type: string;
  severity: string;
  description: string;
}

export interface TaskSummary {
  id: string;
  type: "compliance" | "generation";
  status: string;
  summary: string;
  created_at: string;
  market?: string;
  ethnicity?: string;
  age_group?: string;
  platform?: string;
  media_type?: string;
}

export interface ComplianceTaskDetail extends TaskSummary {
  type: "compliance";
  compliance: {
    risk_percentage: number | null;
    status: string;
    market: string;
    ethnicity?: string;
    age_group?: string;
    media_type?: string;
    violations: ViolationSummary[];
    s3_upload_key: string | null;
    s3_segmented_key: string | null;
    s3_remix_key: string | null;
    result_json: Record<string, unknown> | null;
  };
  pipeline_state?: Record<string, unknown>;
}

export interface GenerationTaskDetail extends TaskSummary {
  type: "generation";
  pipeline_state: PipelineState;
}

export type TaskDetail = ComplianceTaskDetail | GenerationTaskDetail;

export interface ProjectResponse {
  id: string;
  name: string;
  owner_email: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export async function listTasks(projectId: string): Promise<TaskSummary[]> {
  const res = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks`);

  if (res.status === 404) throw new Error("404: Project not found");
  if (res.status === 403) throw new Error("403: Access denied");
  if (!res.ok) throw await toApiRequestError(res, "Tasks could not be retrieved.");

  return res.json();
}

export async function getTask(projectId: string, taskId: string): Promise<TaskDetail> {
  const res = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`);

  if (res.status === 404) throw new Error("404: Task not found");
  if (res.status === 403) throw new Error("403: Access denied");
  if (!res.ok) throw await toApiRequestError(res, "Task could not be retrieved.");
  return res.json();
}

export async function createGenerationTask(projectId: string): Promise<TaskSummary> {
  const res = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "generation" }),
  });

  if (!res.ok) throw await toApiRequestError(res, "Task could not be created.");

  return res.json();
}

export async function savePipeline(
  projectId: string,
  taskId: string,
  state: PipelineState,
  status: string = "saved"
): Promise<void> {
  const res = await authenticatedFetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/pipeline`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, pipeline_state: state }),
    }
  );

  if (!res.ok) throw await toApiRequestError(res, "Task progress could not be saved.");
}

export async function updateProjectName(
  projectId: string,
  name: string
): Promise<ProjectResponse> {
  const res = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!res.ok) throw await toApiRequestError(res, "Project could not be updated.");

  return res.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}`, {
    method: "DELETE",
  });

  if (!res.ok) throw await toApiRequestError(res, "Project could not be deleted.");
}

export async function deleteTask(projectId: string, taskId: string): Promise<void> {
  const res = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`, {
    method: "DELETE",
  });

  if (!res.ok) throw await toApiRequestError(res, "Task could not be deleted.");
}

export async function sendChatWithAgent(
  projectId: string,
  taskId: string,
  message: string,
  referenceUrls: string[] = []
): Promise<Response> {
  return authenticatedFetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, reference_urls: referenceUrls }),
    }
  );
}
