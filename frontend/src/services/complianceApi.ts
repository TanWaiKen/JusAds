/**
 * JusAds Compliance API Service
 * Connects to the LangGraph backend at /api/compliance
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export interface Violation {
  index: number;
  start: number;
  end: number;
  type: "visual" | "audio";
  category: string;
  severity: string;
  description: string;
  clip_url: string | null;
}

export interface Localization {
  language?: string;
  model_talent?: string;
  script_adaptation?: string;
  visual_style?: string;
  platform?: string;
}

export interface Persona {
  base?: {
    demographics?: Record<string, string>;
    core_values?: string[];
    nuances_and_behavior?: string[];
    strict_taboos?: string[];
    historical_and_cultural_context?: string;
  };
  targeted?: {
    label?: string;
    age_range?: string;
    tone_and_language?: string;
    key_motivations?: string[];
    preferred_channels?: string[];
    content_style?: string;
  };
}

export interface ComplianceResult {
  check_id: string;
  video_filename: string;
  market: string;
  ethnicity: string;
  age_group: string;
  score: number;
  risk_level: "High" | "Medium" | "Low";
  explanation: string;
  suggestion: string;
  localization: Localization;
  persona: Persona | null;
  violations: Violation[];
  processing_time_seconds: number;
}

export async function checkCompliance(
  file: File,
  market: string,
  ethnicity: string,
  ageGroup: string
): Promise<ComplianceResult> {
  const formData = new FormData();
  formData.append("video", file);
  formData.append("market", market);
  formData.append("ethnicity", ethnicity);
  formData.append("age_group", ageGroup);

  const res = await fetch(`${API_BASE}/api/compliance/check`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function getComplianceResult(checkId: string): Promise<ComplianceResult> {
  const res = await fetch(`${API_BASE}/api/compliance/${checkId}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Stream compliance check with real-time node status updates.
 * Uses SSE (Server-Sent Events) via POST.
 */
export interface NodeStatus {
  type: "node_status";
  node: string;
  status: "running" | "completed" | "error";
  description: string;
  duration_ms?: number;
}

export interface StreamResult {
  type: "result";
  data: ComplianceResult;
}

export type StreamEvent = NodeStatus | StreamResult;

export async function checkComplianceStream(
  file: File,
  market: string,
  ethnicity: string,
  ageGroup: string,
  onEvent: (event: StreamEvent) => void
): Promise<ComplianceResult> {
  const formData = new FormData();
  formData.append("video", file);
  formData.append("market", market);
  formData.append("ethnicity", ethnicity);
  formData.append("age_group", ageGroup);

  const res = await fetch(`${API_BASE}/api/compliance/check/stream`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let finalResult: ComplianceResult | null = null;
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event = JSON.parse(line.slice(6)) as StreamEvent;
          onEvent(event);
          if (event.type === "result") {
            finalResult = event.data;
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error("Stream ended without result");
  }

  return finalResult;
}

export function getClipUrl(clipUrl: string): string {
  return `${API_BASE}${clipUrl}`;
}
