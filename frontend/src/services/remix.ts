/**
 * Remix SSE client.
 *
 * Kept separate from complianceApi because remediation is an independent,
 * long-running agent workflow with its own result and progress events.
 */
import { API_BASE } from "@/services/complianceApi";

export interface RemixNodeStatus {
  type: "node_status";
  node: string;
  status: "running" | "completed" | "error";
  description: string;
  duration_ms?: number;
}

export interface RemediationVersion {
  id: string;
  number: number;
  media_type: string;
  asset_url?: string;
  created_at: string;
}

export interface RemediationResult {
  type: string;
  rewritten_text?: string;
  voice_id?: string;
  s3_remix_url?: string;
  version?: RemediationVersion;
}

export interface RemixResultEvent {
  type: "remix_result";
  data?: RemediationResult;
}

export interface RemixCompliantEvent {
  type: "compliant";
  message: string;
}

export interface RemixCannotFixEvent {
  type: "cannot_fix";
  guidance: string;
  reasoning: string;
  redirect_to_frontend: boolean;
  violations: string[];
}

export interface RemixImageEditEvent {
  type: "image_edit";
  s3_remix_url: string | null;
  quality_score: number;
  edit_mode: string;
  localization_verified?: boolean;
  required_language?: string;
  localized_copy_actions?: { original: string; replacement: string; bbox: number[] }[];
  bias_check?: { passed: boolean; issues: string[] };
}

export interface RemixEditFailedEvent {
  type: "edit_failed";
  fallback_guidance: string;
  error: string;
}

export interface RemixErrorEvent {
  type: "error";
  message: string;
}

export type RemixStreamEvent =
  | RemixNodeStatus
  | RemixResultEvent
  | RemixCompliantEvent
  | RemixCannotFixEvent
  | RemixImageEditEvent
  | RemixEditFailedEvent
  | RemixErrorEvent;

/** Stream the remix agent's progress and terminal result over SSE. */
export async function streamRemix(
  checkId: string,
  onEvent: (event: RemixStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/compliance/${checkId}/remix`, {
    method: "POST",
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Remix API error: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const consumeLine = (line: string) => {
    if (!line.startsWith("data: ")) return;
    try {
      onEvent(JSON.parse(line.slice(6).trim()) as RemixStreamEvent);
    } catch {
      // A malformed SSE line must not terminate an otherwise valid remix.
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(consumeLine);
  }
  if (buffer.trim()) consumeLine(buffer);
}
