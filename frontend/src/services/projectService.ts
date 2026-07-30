import { API_BASE } from "@/lib/apiConfig";
import { authenticatedFetch, toApiRequestError } from "@/lib/apiAuth";
import type { PipelineState } from "@/components/workspace/canvas/graphModel";
import type { Project, TaskDetail, TaskSummary } from "@/models/project";

export type { Project as ProjectResponse, TaskDetail, TaskSummary } from "@/models/project";

export async function listProjects(signal?: AbortSignal): Promise<Project[]> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects`, { signal });
  if (!response.ok) throw await toApiRequestError(response, "Projects could not be loaded.");
  return response.json() as Promise<Project[]>;
}

export async function createProject(name: string): Promise<Project> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Project could not be created.");
  return response.json() as Promise<Project>;
}

export async function listTasks(projectId: string): Promise<TaskSummary[]> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks`);
  if (response.status === 404) throw new Error("404: Project not found");
  if (response.status === 403) throw new Error("403: Access denied");
  if (!response.ok) throw await toApiRequestError(response, "Tasks could not be retrieved.");
  return response.json();
}

export async function getTask(projectId: string, taskId: string): Promise<TaskDetail> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`);
  if (response.status === 404) throw new Error("404: Task not found");
  if (response.status === 403) throw new Error("403: Access denied");
  if (!response.ok) throw await toApiRequestError(response, "Task could not be retrieved.");
  return response.json();
}

export async function createGenerationTask(projectId: string): Promise<TaskSummary> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "generation" }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Task could not be created.");
  return response.json();
}

export async function savePipeline(projectId: string, taskId: string, state: PipelineState, status = "saved"): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}/pipeline`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, pipeline_state: state }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Task progress could not be saved.");
}

export async function updateProjectName(projectId: string, name: string): Promise<Project> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Project could not be updated.");
  return response.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}`, { method: "DELETE" });
  if (!response.ok) throw await toApiRequestError(response, "Project could not be deleted.");
}

export async function deleteTask(projectId: string, taskId: string): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}`, { method: "DELETE" });
  if (!response.ok) throw await toApiRequestError(response, "Task could not be deleted.");
}

export async function sendChatWithAgent(
  projectId: string,
  taskId: string,
  message: string,
  referenceUrls: string[] = [],
): Promise<Response> {
  return authenticatedFetch(`${API_BASE}/api/projects/${projectId}/tasks/${taskId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, reference_urls: referenceUrls }),
  });
}

export async function shareProject(projectId: string, email: string): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) throw await toApiRequestError(response, "Could not share project.");
}

export interface ProjectMember {
  email: string;
  role: string;
}

export async function listProjectMembers(projectId: string): Promise<ProjectMember[]> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/members`);
  if (!response.ok) throw await toApiRequestError(response, "Could not load project members.");
  const payload = await response.json() as { members?: ProjectMember[] };
  return Array.isArray(payload.members) ? payload.members : [];
}

export async function removeProjectMember(projectId: string, email: string): Promise<void> {
  const response = await authenticatedFetch(`${API_BASE}/api/projects/${projectId}/members/${encodeURIComponent(email)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw await toApiRequestError(response, "Could not remove project member.");
}
