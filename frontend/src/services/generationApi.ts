/**
 * Agentic Ad Studio — Generation API Service
 *
 * All generation API communication is routed through this service layer
 * (Req 10.5). Provides `sendChat` (SSE streaming chat generation) and
 * `getChatHistory` (prior conversation retrieval on task reopen).
 *
 * Connects to the backend at /api/projects/{projectId}/tasks/{taskId}.
 */

import type { PipelineState } from "@/components/workspace/canvas/graphModel";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ─── Types ───────────────────────────────────────────────────────────────────

/** The three supported launch platforms (Req 9.1). */
export type TargetPlatform = "tiktok" | "instagram" | "youtube" | "shopee";

/** Target audience for conditional cultural localization. */
export type TargetEthnicity = "malay" | "chinese" | "indian" | "all";

/** Default platform applied when the user selects none (Req 9.5 / 9.6). */
export const DEFAULT_PLATFORM: TargetPlatform = "tiktok";

/** Frontend-facing compliance status, mapped from backend final/non-final. */
export type ComplianceStatus = "compliant" | "non-compliant" | "pending";

/**
 * The compact "why" behind a compliance verdict, surfaced to the user. Every
 * field is optional — only the ones the backend populated are present.
 */
export interface ComplianceReasons {
  riskLevel?: string;
  riskPercentage?: number;
  explanation?: string;
  suggestion?: string;
  indicators?: string[];
  skipped?: boolean;
  reason?: string;
  error?: string;
}

/** The four supported output media types (Req 11.1). */
export type MediaType = "text" | "image" | "audio" | "video";

/** All media types, in stable display order — the canonical group keys. */
export const MEDIA_TYPES: readonly MediaType[] = [
  "text",
  "image",
  "audio",
  "video",
];

/** A single generated output as presented in the output gallery. */
export interface GeneratedAdView {
  adId: string;
  mediaType: MediaType;
  platform: string;
  publicUrl: string | null;
  caption: string | null;
  complianceStatus: ComplianceStatus; // maps from backend final/non-final (Req 11.2)
  complianceReasons?: ComplianceReasons; // the "why" behind the verdict
}

/**
 * Outputs grouped by media type. Keyed by every `MediaType`, so all four keys
 * always exist; media types with no outputs map to an empty array.
 */
export type GroupedAds = Record<MediaType, GeneratedAdView[]>;

/** A single persisted chat turn returned by the chat-history endpoint. */
export interface ChatMessageView {
  role: "user" | "assistant";
  content: string;
  attachments: unknown[];
  createdAt: string;
}

/**
 * A single planned scene in a Video V2 storyboard (before rendering).
 * Mirrors the backend `plan_video` output.
 */
export interface VideoPlanScene {
  index: number;
  description: string;
  shotType: string;
  cameraMovement: string;
  subtitle: string;
  script: string;
  sfx: string;
  duration: number;
  keyframeS3Key: string;
  keyframeUrl: string;
}

/** A Video V2 storyboard plan awaiting user approval (Continue). */
export interface VideoPlan {
  planId: string;
  brief: string;
  platform: string;
  aspectRatio: string;
  scenes: VideoPlanScene[];
}

/**
 * A parsed Server-Sent Event emitted by the generation orchestrator.
 * Any given event carries a subset of these fields depending on its kind:
 * `{ node, status, data }` | `{ text }` | `{ pipeline_state }` | `{ error }`
 * | `{ video_plan }` (Video V2 storyboard awaiting approval).
 */
export interface SSEEvent {
  node?: string;
  status?: "in-progress" | "completed" | "failed";
  data?: unknown;
  text?: string;
  pipeline_state?: PipelineState;
  video_plan?: unknown;
  error?: string;
}

// ─── API functions ─────────────────────────────────────────────────────────

/**
 * Send a chat generation request and return the raw streaming `Response`.
 *
 * The body always includes a `target_platform`, defaulting to
 * `DEFAULT_PLATFORM` ("instagram") when none is supplied (Req 9.6). The
 * returned `Response` exposes an SSE body the caller consumes line-by-line;
 * the line-by-line `data:` parser is provided separately (task 12.3) and
 * plugs into `response.body`.
 */
/** Extra generation settings passed alongside the chat message. */
export interface GenerationOptions {
  ageGroup?: string;
  market?: string;
  language?: string;
  productName?: string;
  productCategory?: string;
  gender?: string;
}

export async function sendChat(
  projectId: string,
  taskId: string,
  message: string,
  referenceUrls: string[] = [],
  targetPlatform?: TargetPlatform,
  skipCompliance?: boolean,
  videoV3?: boolean,
  targetEthnicity?: TargetEthnicity,
  options?: GenerationOptions
): Promise<Response> {
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        reference_urls: referenceUrls,
        target_platform: targetPlatform ?? DEFAULT_PLATFORM,
        skip_compliance: skipCompliance ?? false,
        video_v3: videoV3 ?? false,
        target_ethnicity: targetEthnicity ?? "all",
        age_group: options?.ageGroup ?? "all_ages",
        market: options?.market ?? "malaysia",
        language: options?.language ?? "auto",
        product_name: options?.productName ?? "",
        product_category: options?.productCategory ?? "",
        gender: options?.gender ?? "female",
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status} ${response.statusText}`);
  }

  return response;
}

/**
 * Parse a streaming SSE `Response` body into an ordered sequence of `SSEEvent`s.
 *
 * Consumes `response.body` via a `ReadableStream` reader and `TextDecoder`,
 * buffering partial lines across chunk boundaries and splitting on newlines
 * (Req 10.1 — line-by-line parsing over a ReadableStream). Events are yielded
 * in the exact order received, so ordering is preserved.
 *
 * The parser is failure-tolerant (Req 10.6): any line that is not a
 * well-formed `data: {json}` line — missing prefix, invalid JSON, or a
 * non-object payload — is skipped, and parsing continues with subsequent
 * lines. The generator never throws; a reader error terminates iteration
 * cleanly while preserving every event already yielded.
 *
 * A `null` body (e.g. a response with no stream) yields no events.
 */
export async function* parseSSEStream(
  response: Response
): AsyncGenerator<SSEEvent> {
  const body = response.body;
  if (body === null) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch {
        // A reader/network error ends the stream without throwing; events
        // already yielded are preserved (Req 10.6 / 10.7 boundary).
        break;
      }

      if (chunk.done) break;

      buffer += decoder.decode(chunk.value, { stream: true });
      const lines = buffer.split("\n");
      // Keep the trailing partial line in the buffer for the next chunk.
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const event = parseSSELine(line);
        if (event !== null) yield event;
      }
    }

    // Flush any complete line left in the buffer once the stream ends.
    buffer += decoder.decode();
    const trailing = parseSSELine(buffer);
    if (trailing !== null) yield trailing;
  } finally {
    reader.releaseLock();
  }
}

/**
 * Parse a single raw SSE line into an `SSEEvent`, or `null` when the line is
 * not a well-formed `data:`-prefixed JSON object.
 *
 * Never throws — malformed input yields `null` so callers can skip it.
 */
function parseSSELine(line: string): SSEEvent | null {
  const trimmed = line.trimEnd(); // tolerate CRLF line endings
  if (!trimmed.startsWith("data:")) return null;

  const payload = trimmed.slice(5).trim();
  if (payload === "") return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch {
    return null;
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return null;
  }

  return parsed as SSEEvent;
}

/**
 * Send a chat generation request and iterate its parsed SSE events.
 *
 * Convenience wrapper that combines `sendChat` (task 12.1) with
 * `parseSSEStream`, so consumers can `for await` well-formed `SSEEvent`s in
 * order without touching the raw `Response`. `sendChat` still throws on a
 * non-ok response; once streaming begins, malformed lines are skipped and the
 * parser never throws (Req 10.1 / 10.6).
 */
export async function* streamChat(
  projectId: string,
  taskId: string,
  message: string,
  referenceUrls: string[] = [],
  targetPlatform?: TargetPlatform,
  skipCompliance?: boolean,
  videoV3?: boolean,
  targetEthnicity?: TargetEthnicity,
  options?: GenerationOptions
): AsyncGenerator<SSEEvent> {
  const response = await sendChat(
    projectId,
    taskId,
    message,
    referenceUrls,
    targetPlatform,
    skipCompliance,
    videoV3,
    targetEthnicity,
    options
  );
  yield* parseSSEStream(response);
}

/**
 * Retrieve the ordered prior chat history for a task (Req 11.5).
 *
 * Returns the persisted turns in creation order. Non-ok responses throw so
 * callers can surface a load-error indication without altering already-shown
 * outputs (Req 11.6).
 */
export async function getChatHistory(
  projectId: string,
  taskId: string
): Promise<ChatMessageView[]> {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/chat-history`
  );

  if (res.status === 404) throw new Error("404: Task not found");
  if (res.status === 503) throw new Error("503: Chat history store unavailable");
  if (!res.ok) {
    throw new Error(`Chat history API error: ${res.status} ${res.statusText}`);
  }

  const payload: unknown = await res.json();
  return normalizeChatHistory(payload);
}

/**
 * Retrieve persisted generated ads for a task, so the Output Gallery can
 * repopulate on page reload without re-generating (Phase B1).
 */
export async function getGeneratedAds(
  projectId: string,
  taskId: string
): Promise<GeneratedAdView[]> {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/generated-ads`
  );
  if (!res.ok) return [];
  const payload: unknown = await res.json();
  if (typeof payload !== "object" || payload === null) return [];
  const raw = (payload as Record<string, unknown>).ads;
  if (!Array.isArray(raw)) return [];

  const views: GeneratedAdView[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;
    const mediaType = typeof record.media_type === "string" ? record.media_type : "";
    if (!["text", "image", "audio", "video"].includes(mediaType)) continue;

    views.push({
      adId: typeof record.ad_id === "string" ? record.ad_id : `ad-${views.length}`,
      mediaType: mediaType as MediaType,
      platform: typeof record.platform === "string" ? record.platform : "",
      publicUrl: typeof record.public_url === "string" ? record.public_url : null,
      caption: typeof record.caption === "string" ? record.caption : null,
      complianceStatus: mapComplianceBadge(
        typeof record.compliance_status === "string" ? record.compliance_status : ""
      ),
      complianceReasons: normalizeComplianceReasons(record.compliance_reasons),
    });
  }
  return views;
}

/** Outcome of a publish request, mirroring the backend `PublishResult`. */
export interface PublishResult {
  adId: string;
  status: string;
  complianceStatus: string;
  alreadyPublished: boolean;
}

/**
 * Approve and publish a generated ad — the human-in-the-loop gate.
 *
 * Flips the ad's backend status to `published` once the owner has reviewed it.
 * Throws with a descriptive message on the known failure paths so the caller
 * can surface them: 404 (ad not found), 409 (blocked — failed compliance), and
 * 503 (persistence store unavailable).
 */
export async function publishAd(
  projectId: string,
  taskId: string,
  adId: string
): Promise<PublishResult> {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/ads/${adId}/publish`,
    { method: "POST" }
  );

  if (!res.ok) {
    let message = `Publish failed: ${res.status} ${res.statusText}`;
    try {
      const body: unknown = await res.json();
      if (
        typeof body === "object" &&
        body !== null &&
        typeof (body as Record<string, unknown>).error === "string"
      ) {
        message = (body as Record<string, string>).error;
      }
    } catch {
      // Non-JSON error body — keep the status-line message.
    }
    throw new Error(message);
  }

  const payload = (await res.json()) as Record<string, unknown>;
  return {
    adId: typeof payload.ad_id === "string" ? payload.ad_id : adId,
    status: typeof payload.status === "string" ? payload.status : "published",
    complianceStatus:
      typeof payload.compliance_status === "string"
        ? payload.compliance_status
        : "non-final",
    alreadyPublished: payload.already_published === true,
  };
}

/** Result of a distribution request. */
export interface DistributeResult {
  postId: string;
  status: string;
  platform: string;
}

/**
 * Distribute a published ad to a social platform via Zernio.
 *
 * Only works on ads with ``status = published``. Throws with a descriptive
 * message on 404 (not found), 409 (not published / no account), and 503
 * (Zernio unavailable / not configured).
 */
export async function distributeAd(
  projectId: string,
  taskId: string,
  adId: string,
  platform: string,
  caption?: string
): Promise<DistributeResult> {
  const res = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/ads/${adId}/distribute`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, caption: caption ?? "" }),
    }
  );

  if (!res.ok) {
    let message = `Distribute failed: ${res.status} ${res.statusText}`;
    try {
      const body: unknown = await res.json();
      if (typeof body === "object" && body !== null && typeof (body as Record<string, unknown>).error === "string") {
        message = (body as Record<string, string>).error;
      }
    } catch { /* keep status-line message */ }
    throw new Error(message);
  }

  const payload = (await res.json()) as Record<string, unknown>;
  return {
    postId: typeof payload.post_id === "string" ? payload.post_id : "",
    status: typeof payload.status === "string" ? payload.status : "distributed",
    platform: typeof payload.platform === "string" ? payload.platform : platform,
  };
}

// ─── Output display helpers ──────────────────────────────────────────────────

/**
 * Group generated outputs by media type as a faithful partition (Req 8.6,
 * 10.4, 11.1).
 *
 * The result is keyed by every `MediaType`, so all four groups always exist;
 * a media type with no outputs maps to an empty array. Every input ad appears
 * exactly once, in exactly the group matching its own `mediaType` — none are
 * lost or duplicated, and input order within each group is preserved.
 */
export function groupAdsByMediaType(ads: GeneratedAdView[]): GroupedAds {
  const grouped: GroupedAds = {
    text: [],
    image: [],
    audio: [],
    video: [],
  };

  for (const ad of ads) {
    grouped[ad.mediaType].push(ad);
  }

  return grouped;
}

/**
 * Map a backend compliance status string to a frontend badge status (Req
 * 11.2).
 *
 * Total by construction: `final-compliant → compliant`,
 * `final-non-compliant → non-compliant`, `non-final → pending`, and any
 * unknown/unexpected value falls back to `pending` (safe default) so this
 * function never throws.
 */
export function mapComplianceBadge(backendStatus: string): ComplianceStatus {
  switch (backendStatus) {
    case "final-compliant":
      return "compliant";
    case "final-non-compliant":
      return "non-compliant";
    case "non-final":
      return "pending";
    default:
      return "pending";
  }
}

// ─── Guided Generation ───────────────────────────────────────────────────────

/**
 * Submit a guided generation request and return the raw streaming `Response`.
 *
 * Used by the guided form flow: after creating a task and navigating to the
 * canvas, this function POSTs the structured form data with `guided_mode: true`
 * to the chat endpoint. The backend assembles the fixed prompt from guided
 * inputs before passing to the orchestrator.
 */
export async function submitGuidedGeneration(
  projectId: string,
  taskId: string,
  designType: string,
  guidedInputs: Record<string, string>,
  referenceUrls: string[] = []
): Promise<Response> {
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: `Generate ${designType} for ${guidedInputs.product_name || "product"}`,
        guided_mode: true,
        design_type: designType,
        guided_inputs: guidedInputs,
        reference_urls: referenceUrls,
        target_platform: guidedInputs.platform || undefined,
        product_name: guidedInputs.product_name || undefined,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Guided generation error: ${response.status} ${response.statusText}`);
  }

  return response;
}

/**
 * Submit a guided generation request and iterate its parsed SSE events.
 *
 * Convenience wrapper combining `submitGuidedGeneration` with `parseSSEStream`
 * for consumers that want to `for await` over well-typed events.
 */
export async function* streamGuidedGeneration(
  projectId: string,
  taskId: string,
  designType: string,
  guidedInputs: Record<string, string>,
  referenceUrls: string[] = []
): AsyncGenerator<SSEEvent> {
  const response = await submitGuidedGeneration(
    projectId,
    taskId,
    designType,
    guidedInputs,
    referenceUrls
  );
  yield* parseSSEStream(response);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Narrow a raw backend `video_plan` object into a `VideoPlan`.
 *
 * Maps snake_case backend keys to the camelCase frontend shape and validates
 * each scene. Returns `undefined` when the payload isn't a usable plan (so
 * callers can simply check for presence). Never throws.
 */
export function normalizeVideoPlan(raw: unknown): VideoPlan | undefined {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return undefined;
  const record = raw as Record<string, unknown>;
  const rawScenes = record.scenes;
  if (!Array.isArray(rawScenes)) return undefined;

  const scenes: VideoPlanScene[] = [];
  for (const entry of rawScenes) {
    if (typeof entry !== "object" || entry === null) continue;
    const s = entry as Record<string, unknown>;
    scenes.push({
      index: typeof s.index === "number" ? s.index : scenes.length,
      description: typeof s.description === "string" ? s.description : "",
      shotType: typeof s.shot_type === "string" ? s.shot_type : "",
      cameraMovement: typeof s.camera_movement === "string" ? s.camera_movement : "",
      subtitle: typeof s.subtitle === "string" ? s.subtitle : "",
      script: typeof s.script === "string" ? s.script : "",
      sfx: typeof s.sfx === "string" ? s.sfx : "",
      duration: typeof s.duration === "number" ? s.duration : 5,
      keyframeS3Key: typeof s.keyframe_s3_key === "string" ? s.keyframe_s3_key : "",
      keyframeUrl: typeof s.keyframe_url === "string" ? s.keyframe_url : "",
    });
  }

  if (scenes.length === 0) return undefined;

  return {
    planId: typeof record.plan_id === "string" ? record.plan_id : "",
    brief: typeof record.brief === "string" ? record.brief : "",
    platform: typeof record.platform === "string" ? record.platform : "",
    aspectRatio: typeof record.aspect_ratio === "string" ? record.aspect_ratio : "9:16",
    scenes,
  };
}

/**
 * Serialize a (possibly user-edited) `VideoPlan` back to the backend snake_case
 * shape expected by the execute-video-plan endpoint.
 */
function serializeVideoPlan(plan: VideoPlan): Record<string, unknown> {
  return {
    plan_id: plan.planId,
    brief: plan.brief,
    platform: plan.platform,
    aspect_ratio: plan.aspectRatio,
    scenes: plan.scenes.map((s) => ({
      index: s.index,
      description: s.description,
      shot_type: s.shotType,
      camera_movement: s.cameraMovement,
      subtitle: s.subtitle,
      script: s.script,
      sfx: s.sfx,
      duration: s.duration,
      keyframe_s3_key: s.keyframeS3Key,
      keyframe_url: s.keyframeUrl,
    })),
  };
}

/**
 * Execute an approved Video V2 storyboard plan (the "Continue" action) and
 * iterate its parsed SSE events. Runs the expensive Veo/ffmpeg render on the
 * backend and streams `{node,status,data}` progress then `{pipeline_state}`.
 */
export async function* executeVideoPlan(
  projectId: string,
  taskId: string,
  plan: VideoPlan,
  skipCompliance?: boolean
): AsyncGenerator<SSEEvent> {
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/execute-video-plan`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: serializeVideoPlan(plan),
        skip_compliance: skipCompliance ?? false,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Execute plan error: ${response.status} ${response.statusText}`);
  }

  yield* parseSSEStream(response);
}


/**
 * Narrow a raw backend `compliance_reasons` object into `ComplianceReasons`.
 *
 * Backend keys are snake_case (`risk_level`, `risk_percentage`); this maps them
 * to the camelCase frontend shape, keeping only well-typed, populated fields.
 * Returns `undefined` when there is nothing meaningful to show, so callers can
 * simply check for presence. Never throws.
 */
export function normalizeComplianceReasons(raw: unknown): ComplianceReasons | undefined {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return undefined;
  const record = raw as Record<string, unknown>;
  const reasons: ComplianceReasons = {};

  if (typeof record.risk_level === "string") reasons.riskLevel = record.risk_level;
  if (typeof record.risk_percentage === "number") reasons.riskPercentage = record.risk_percentage;
  if (typeof record.explanation === "string") reasons.explanation = record.explanation;
  if (typeof record.suggestion === "string") reasons.suggestion = record.suggestion;
  if (Array.isArray(record.indicators)) {
    const indicators = record.indicators.filter(
      (i): i is string => typeof i === "string"
    );
    if (indicators.length > 0) reasons.indicators = indicators;
  }
  if (record.skipped === true) reasons.skipped = true;
  if (typeof record.reason === "string") reasons.reason = record.reason;
  if (typeof record.error === "string") reasons.error = record.error;

  return Object.keys(reasons).length > 0 ? reasons : undefined;
}

/**
 * Narrow an unknown JSON payload into `ChatMessageView[]`.
 *
 * The backend returns `{ messages: [{ role, content, attachments, created_at }] }`.
 * Malformed entries are skipped so a partially valid payload still loads.
 */
function normalizeChatHistory(payload: unknown): ChatMessageView[] {
  const rawMessages = extractMessages(payload);
  const result: ChatMessageView[] = [];

  for (const entry of rawMessages) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;

    const role = record.role;
    if (role !== "user" && role !== "assistant") continue;

    const content = typeof record.content === "string" ? record.content : "";
    const attachments = Array.isArray(record.attachments)
      ? (record.attachments as unknown[])
      : [];
    const createdAt =
      typeof record.created_at === "string"
        ? record.created_at
        : typeof record.createdAt === "string"
          ? record.createdAt
          : "";

    result.push({ role, content, attachments, createdAt });
  }

  return result;
}

/** Extract the message array from either `{ messages: [...] }` or a bare array. */
function extractMessages(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (typeof payload === "object" && payload !== null) {
    const messages = (payload as Record<string, unknown>).messages;
    if (Array.isArray(messages)) return messages;
  }
  return [];
}
