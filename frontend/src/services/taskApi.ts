/**
 * Task API Service
 * Connects to the project tasks backend at /api/projects/{projectId}/tasks
 */

import type { PipelineState } from "@/components/workspace/canvas/graphModel";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

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

export async function listTasks(projectId: string, username?: string): Promise<TaskSummary[]> {
  const url = username
    ? `${API_BASE}/api/projects/${projectId}/tasks?username=${encodeURIComponent(username)}`
    : `${API_BASE}/api/projects/${projectId}/tasks`;
  const res = await fetch(url);

  if (res.status === 404) throw new Error("404: Project not found");
  if (res.status === 403) throw new Error("403: Access denied");
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function getTask(projectId: string, taskId: string): Promise<TaskDetail> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`);

  if (res.status === 404) throw new Error("404: Task not found");
  if (res.status === 403) throw new Error("403: Access denied");
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function createGenerationTask(projectId: string): Promise<TaskSummary> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "generation" }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function savePipeline(
  projectId: string,
  taskId: string,
  state: PipelineState,
  status: string = "saved"
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/pipeline`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, pipeline_state: state }),
    }
  );

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
}

export async function updateProjectName(
  projectId: string,
  name: string
): Promise<ProjectResponse> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
}

export async function deleteTask(projectId: string, taskId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
}

export async function sendChatWithAgent(
  projectId: string,
  taskId: string,
  message: string,
  referenceUrls: string[] = []
): Promise<Response> {
  return fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, reference_urls: referenceUrls }),
    }
  );
}
