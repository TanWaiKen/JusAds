/**
 * JusAds Compliance API Service
 * Connects to the LangGraph backend at /api/compliance
 */

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export interface Violation {
  index: number;
  start: number;
  end: number;
  type: "visual" | "audio" | "text";
  category: string;
  severity: string;
  description: string;
  clip_url: string | null;
  // Legacy fields from image/text/audio responses (before backend normalization)
  component?: string;
  phrase?: string;
  spoken_phrase?: string;
  location_description?: string;
  edit_prompt?: string;
  reason?: string;
  suggested_replacement?: string;
}

/**
 * Normalizes a raw violation object from the API into the shape the frontend expects.
 * Handles the case where image/text/audio responses use different field names.
 */
export function normalizeViolation(raw: Record<string, unknown>, index: number): Violation {
  return {
    index: (raw.index as number) ?? index,
    start: (raw.start as number) ?? 0,
    end: (raw.end as number) ?? 0,
    type: (raw.type as Violation["type"]) ?? "visual",
    category: (raw.category as string) ?? "Compliance Issue",
    severity: (raw.severity as string) ?? "warning",
    description:
      (raw.description as string) ||
      (raw.component as string) ||
      (raw.phrase as string) ||
      (raw.spoken_phrase as string) ||
      "",
    clip_url: (raw.clip_url as string) ?? null,
    component: raw.component as string | undefined,
    phrase: raw.phrase as string | undefined,
    spoken_phrase: raw.spoken_phrase as string | undefined,
    location_description: raw.location_description as string | undefined,
    edit_prompt: raw.edit_prompt as string | undefined,
    reason: raw.reason as string | undefined,
    suggested_replacement: raw.suggested_replacement as string | undefined,
  };
}

/**
 * Normalizes the violations array in a ComplianceResult.
 * Also synthesizes violations from high_risk_indicators if violations is empty.
 */
export function normalizeViolations(result: ComplianceResult): Violation[] {
  // If violations exist, normalize them
  if (result.violations && result.violations.length > 0) {
    return result.violations.map((v, i) => normalizeViolation(v as unknown as Record<string, unknown>, i));
  }

  // Fallback: synthesize from high_risk_indicators
  const indicators = (result as unknown as Record<string, unknown>).high_risk_indicators as string[] | undefined;
  if (indicators && indicators.length > 0) {
    return indicators.map((indicator, i) => ({
      index: i,
      start: 0,
      end: 0,
      type: "visual" as const,
      category: "Compliance Issue",
      severity: result.risk_level === "High" ? "error" : "warning",
      description: indicator,
      clip_url: null,
    }));
  }

  return [];
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

export interface ResearchSource {
  url: string;
  title?: string;
  snippet?: string;
  provider?: "google_grounding" | "tavily";
}

export interface VerificationResult {
  research_report: string;
  sources: ResearchSource[];
  citation_urls?: string[];
  sources_count: number;
  overall_confidence: "high" | "medium" | "low";
  violations_checked?: number;
  provider?: string;
  skipped?: boolean;
}

export interface TextAnnotation {
  start: number;
  end: number;
  text: string;
  reason: string;
  render: "underline" | "bold";
}

export interface TranscriptSegment {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface ImageCopyAction {
  original: string;
  replacement: string;
  language: string;
  reason: string;
}

export interface ImageReview {
  copy_actions: ImageCopyAction[];
  character_assessment: string;
  claims_requiring_evidence: string[];
  sensitive_content: string[];
}

export interface ComplianceResult {
  check_id: string;
  video_filename: string;
  market: string;
  ethnicity: string;
  age_group: string;
  platform?: string;
  // New risk percentage fields
  risk_percentage: number;    // 0-100, probability of cultural backlash
  risk_band: "Low" | "Moderate" | "High" | "Critical";
  confidence: "high" | "moderate" | "low";
  // Backward compat fields
  score: number;              // 100 - risk_percentage
  risk_level: "High" | "Medium" | "Low" | "Moderate" | "Critical";
  compliance_verdict?: "accepted" | "needs_remediation" | "rejected";
  explanation: string;
  suggestion: string;
  localization: Localization;
  localization_plan?: string;
  persona: Persona | null;
  violations: Violation[];
  high_risk_indicators?: string[];
  high_risk_indicator?: string[];
  verification?: VerificationResult;
  violations_timeline?: { start?: number; end?: number; start_seconds?: number; end_seconds?: number; type?: string; description?: string; severity?: string; clip_url?: string }[];
  segmentation?: { segmented_image_path?: string; detections?: unknown[]; num_masks?: number };
  image_review?: ImageReview;
  text_annotations?: TextAnnotation[];
  audio_annotations?: { segments: TranscriptSegment[]; violations: ComplianceResult["violations_timeline"] };
  violation_clips?: { index: number; start: number; end: number; type: string; description: string; clip_path?: string; clip_url?: string }[];
  _transcript?: { language: string; transcript: string; segments?: TranscriptSegment[] };
  s3_upload_key?: string;
  s3_remix_key?: string;
  s3_segmented_key?: string;
  processing_time_seconds: number;
}

export async function checkCompliance(
  file: File | null,
  market: string,
  ethnicity: string,
  ageGroup: string,
  platform: string = "general",
  text?: string
): Promise<ComplianceResult> {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  } else if (text) {
    formData.append("text", text);
  }
  formData.append("market", market);
  formData.append("ethnicity", ethnicity);
  formData.append("age_group", ageGroup);
  formData.append("platform", platform);

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
  file: File | null,
  market: string,
  ethnicity: string,
  ageGroup: string,
  platform: string = "general",
  onEvent: (event: StreamEvent) => void,
  text?: string
): Promise<ComplianceResult> {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  } else if (text) {
    formData.append("text", text);
  }
  formData.append("market", market);
  formData.append("ethnicity", ethnicity);
  formData.append("age_group", ageGroup);
  formData.append("platform", platform);

  const res = await fetch(`${API_BASE}/api/compliance/check`, {
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

/**
 * Stream a remix/remediation request for a compliance check.
 * Calls POST /api/compliance/{checkId}/remix and streams node status events.
 */
export interface RemixResult {
  type: "remix_result";
  data?: RemediationResult;
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

/** Image passes compliance — no fix needed */
export interface RemixCompliantEvent {
  type: "compliant";
  message: string;
}

/** Product/concept is the violation — cannot auto-fix */
export interface RemixCannotFixEvent {
  type: "cannot_fix";
  guidance: string;
  reasoning: string;
  redirect_to_frontend: boolean;
  violations: string[];
}

/** Edit succeeded — image has been remediated */
export interface RemixImageEditEvent {
  type: "image_edit";
  s3_remix_url: string | null;
  quality_score: number;
  edit_mode: string;
  bias_check?: {
    passed: boolean;
    issues: string[];
  };
}

/** All edit attempts failed */
export interface RemixEditFailedEvent {
  type: "edit_failed";
  fallback_guidance: string;
  error: string;
}

/** SSE error event */
export interface RemixErrorEvent {
  type: "error";
  message: string;
}

export type RemixStreamEvent =
  | NodeStatus
  | RemixResult
  | RemixCompliantEvent
  | RemixCannotFixEvent
  | RemixImageEditEvent
  | RemixEditFailedEvent
  | RemixErrorEvent;

export async function remixComplianceStream(
  checkId: string,
  onEvent: (event: RemixStreamEvent) => void
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/compliance/${checkId}/remix`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(`Remix API error: ${res.status} ${res.statusText}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
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
          const event = JSON.parse(line.slice(6)) as RemixStreamEvent;
          onEvent(event);
        } catch {
          // skip malformed lines
        }
      }
    }
  }
}
