import { useState, useRef, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { consumePrefill } from "@/lib/sessionStorage";
import { searchPromptLibrary, uploadProjectReference } from "@/services/mediaService";
import {
  streamChat,
  getChatHistory,
  getGeneratedAds,
  mapComplianceBadge,
  normalizeComplianceReasons,
  normalizeVideoPlan,
  DEFAULT_PLATFORM,
  type TargetPlatform,
  type TargetEthnicity,
  type GeneratedAdView,
  type MediaType,
  type VideoPlan,
  type GenerationOptions,
} from "@/services/generationService";
import type { PipelineState, NodeType } from "@/components/workspace/canvas/graphModel";
import {
  Send,
  Bot,
  User,
  Paperclip,
  FileCheck,
  Loader2,
  AlertTriangle,
  Sparkles,
  CheckCircle2,
  Circle,
} from "lucide-react";

interface Message {
  sender: "user" | "agent";
  text: string;
  timestamp: Date;
}

interface ChatbotPanelProps {
  projectId: string;
  taskId: string;
  onStateUpdate: (pipeline: PipelineState) => void;
  targetPlatform: TargetPlatform | null;
  complianceEnabled: boolean;
  targetEthnicity: TargetEthnicity;
  generationOptions: GenerationOptions;
  initialPipelineState?: PipelineState;
  onOutputsUpdate?: (ads: GeneratedAdView[]) => void;
  onVideoPlanUpdate?: (plan: VideoPlan | null, revealOutputs?: boolean) => void;
  triggerPrompt?: string | null;
  onTriggerPromptUsed?: () => void;
  revisionContext?: Pick<GenerationOptions, "parentAdId" | "parentAssetUrl"> | null;
  onRevisionContextUsed?: () => void;
  /** Active reference URLs from canvas reference nodes — overrides local upload state when provided. */
  canvasReferenceUrls?: string[];
  /** Called when the user uploads a new file — canvas should create a reference node. */
  onReferenceUploaded?: (filename: string, url: string) => void;
}

const WELCOME_MESSAGE: Message = {
  sender: "agent",
  text: "Hey! I'm your AI Ad Creator. 🎬\n\nTell me what you'd like to promote and I'll design the ad for you. Here are some ways to start:\n\n• *\"Create a TikTok video ad for my boba shop called Tiger Sugar\"*\n• *\"I need an Instagram post for a Hari Raya sale — 30% off\"*\n• *\"Make a Shopee product video for baby diapers, RM25.90\"*\n\nJust describe your product or paste your idea — even one sentence works! I'll ask if I need more details.\n\n💡 **Tip:** Upload a product photo or brand logo below for better results.",
  timestamp: new Date(),
};

/** Media types recognised when mapping backend `generated_ads` entries. */
const VALID_MEDIA_TYPES: ReadonlySet<string> = new Set<MediaType>([
  "text",
  "image",
  "audio",
  "video",
]);

/**
 * Map the backend orchestrator's `generated_ads` array (attached to the final
 * `pipeline_state`) into `GeneratedAdView[]` for the output gallery (Req 11.1).
 */
export function mapGeneratedAds(pipeline: PipelineState): GeneratedAdView[] {
  const raw = (pipeline as unknown as { generated_ads?: unknown }).generated_ads;
  if (!Array.isArray(raw)) return [];

  const views: GeneratedAdView[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;

    const mediaType = typeof record.media_type === "string" ? record.media_type : "";
    if (!VALID_MEDIA_TYPES.has(mediaType)) continue;

    const adId =
      typeof record.ad_id === "string" && record.ad_id !== ""
        ? record.ad_id
        : typeof record.id === "string" && record.id !== ""
        ? record.id
        : `${mediaType}-${views.length}`;

    views.push({
      adId,
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

/**
 * Detects whether a block of lines looks like a Markdown pipe table.
 * Returns true if at least two lines contain `|` and a separator row exists.
 */
function isPipeTable(lines: string[]): boolean {
  const tableLines = lines.filter((l) => l.trim().startsWith("|") || l.includes("|"));
  return tableLines.length >= 2 && lines.some((l) => /^\|?[\s\-:]+\|/.test(l.trim()));
}

/**
 * Render a block of pipe-table lines into an HTML table string.
 * Handles `| col | col |` rows and `| :--- | :--- |` separator rows.
 */
function renderPipeTable(lines: string[]): string {
  const rows = lines
    .filter((l) => l.trim().length > 0)
    .map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));

  if (rows.length < 2) return lines.join("\n");

  const [headerRow, , ...bodyRows] = rows; // row[1] is the separator — skip it

  const th = (headerRow ?? [])
    .map((cell) => `<th class="px-3 py-2 text-left text-[11px] font-semibold text-primary border-b border-border bg-muted/60">${cell}</th>`)
    .join("");

  const trs = bodyRows
    .map((cells) => {
      const tds = cells
        .map((cell) => `<td class="px-3 py-2 text-xs text-foreground border-b border-border/50 align-top">${cell}</td>`)
        .join("");
      return `<tr class="hover:bg-muted/20 transition-colors">${tds}</tr>`;
    })
    .join("");

  return `<div class="overflow-x-auto rounded-md border border-border my-2"><table class="w-full border-collapse text-left"><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`;
}

/** Lightweight Markdown-to-HTML renderer for agent messages — supports headings, bold, italic, lists, links, and pipe tables. */
function renderMarkdown(text: string) {
  if (!text) return "";

  // Split into blocks so we can detect and render pipe tables as a unit
  const lines = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .split("\n");

  const outputLines: string[] = [];
  let tableBuffer: string[] = [];

  const flushTable = () => {
    if (tableBuffer.length > 0) {
      outputLines.push(renderPipeTable(tableBuffer));
      tableBuffer = [];
    }
  };

  for (const line of lines) {
    const isPipeRow = line.trim().startsWith("|") || (line.includes("|") && /^\|?[\s\-:]+\|/.test(line.trim()));

    if (isPipeRow) {
      tableBuffer.push(line);
    } else {
      if (tableBuffer.length > 0 && isPipeTable(tableBuffer)) {
        flushTable();
      } else {
        // Not a real table — dump buffer as plain lines
        outputLines.push(...tableBuffer);
        tableBuffer = [];
      }
      outputLines.push(line);
    }
  }

  // Flush any trailing table
  if (tableBuffer.length > 0) {
    if (isPipeTable(tableBuffer)) {
      flushTable();
    } else {
      outputLines.push(...tableBuffer);
    }
  }

  let html = outputLines.join("\n");

  // Inline markdown (applied after table HTML is already in place)
  html = html.replace(/^### (.*?)$/gm, '<h3 class="text-xs font-bold text-primary mt-2 mb-0.5">$1</h3>');
  html = html.replace(/^## (.*?)$/gm, '<h2 class="text-sm font-bold text-primary mt-3 mb-1">$1</h2>');
  html = html.replace(/^# (.*?)$/gm, '<h1 class="text-base font-bold text-primary mt-4 mb-1.5">$1</h1>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');
  html = html.replace(/^\s*[-*]\s+(.*?)$/gm, '<li class="ml-4 list-disc text-xs my-0.5">$1</li>');
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline font-medium">$1</a>');

  return <div dangerouslySetInnerHTML={{ __html: html }} className="space-y-1 text-sm leading-relaxed" />;
}

export function ChatbotPanel({
  projectId,
  taskId,
  onStateUpdate,
  targetPlatform,
  complianceEnabled,
  targetEthnicity,
  generationOptions,
  initialPipelineState,
  onOutputsUpdate,
  onVideoPlanUpdate,
  triggerPrompt,
  onTriggerPromptUsed,
  revisionContext,
  onRevisionContextUsed,
  canvasReferenceUrls,
  onReferenceUploaded,
}: ChatbotPanelProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  
  // React to external prompt trigger (e.g. from Inspector revision or Prompt Library)
  useEffect(() => {
    if (triggerPrompt) {
      setInput(triggerPrompt);
      onTriggerPromptUsed?.();
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }, [triggerPrompt, onTriggerPromptUsed]);
  // Persist draft input + references in localStorage so they survive page navigation
  const storageKey = `draft_${projectId}_${taskId}`;

  const [input, setInput] = useState(() => {
    try { return localStorage.getItem(`${storageKey}_input`) || ""; } catch { return ""; }
  });
  const [loading, setLoading] = useState(false);
  const [references, setReferences] = useState<{ filename: string; url: string }[]>(() => {
    try {
      const saved = localStorage.getItem(`${storageKey}_refs`);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  // Track which references are selected to be passed to AI on the next send.
  // New uploads are auto-selected. Stored as a Set of URLs.
  const [selectedRefUrls, setSelectedRefUrls] = useState<Set<string>>(() => {
    try {
      const savedRefs = localStorage.getItem(`${storageKey}_refs`);
      const savedSel = localStorage.getItem(`${storageKey}_sel`);
      if (savedSel) {
        const parsed: unknown = JSON.parse(savedSel);
        if (Array.isArray(parsed)) return new Set(parsed as string[]);
      }
      // Default: all saved references are selected
      if (savedRefs) {
        const refs: { filename: string; url: string }[] = JSON.parse(savedRefs);
        return new Set(refs.map((r) => r.url));
      }
    } catch { /* ignore */ }
    return new Set<string>();
  });

  const toggleRefSelection = useCallback((url: string) => {
    setSelectedRefUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
      } else {
        next.add(url);
      }
      return next;
    });
  }, []);

  // On mount: check sessionStorage for prefill data (from "Try Now" flow)
  const prefillConsumed = useRef(false);
  useEffect(() => {
    if (prefillConsumed.current) return;
    prefillConsumed.current = true;
    const prefill = consumePrefill();
    if (prefill) {
      setInput(prefill.prompt);
      if (prefill.referenceImageUrl) {
        setReferences((prev) => [
          ...prev,
          { filename: prefill.referenceImageLabel || "Reference Image", url: prefill.referenceImageUrl! },
        ]);
        setSelectedRefUrls((prev) => new Set([...prev, prefill.referenceImageUrl!]));
      }
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, []);

  // Auto-save draft input to localStorage on change
  useEffect(() => {
    try { localStorage.setItem(`${storageKey}_input`, input); } catch {}
  }, [input, storageKey]);

  // Auto-save references to localStorage on change
  useEffect(() => {
    try { localStorage.setItem(`${storageKey}_refs`, JSON.stringify(references)); } catch {}
  }, [references, storageKey]);

  // Auto-save selected ref URLs to localStorage on change
  useEffect(() => {
    try { localStorage.setItem(`${storageKey}_sel`, JSON.stringify(Array.from(selectedRefUrls))); } catch {}
  }, [selectedRefUrls, storageKey]);
  const [uploading, setUploading] = useState(false);
  const [genStatus, setGenStatus] = useState<string | null>(null);
  const [streamError, setStreamError] = useState(false);
  const [historyError, setHistoryError] = useState(false);

  // Wrapped setters that also notify the parent (lifted state for Outputs tab).
  const setOutputs = (ads: GeneratedAdView[]): void => {
    onOutputsUpdate?.(ads);
  };
  const setVideoPlan = (plan: VideoPlan | null, revealOutputs = true): void => {
    onVideoPlanUpdate?.(plan, revealOutputs);
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [showAtPicker, setShowAtPicker] = useState(false);
  const [showPromptSearch, setShowPromptSearch] = useState(false);
  const [autoSuggestions, setAutoSuggestions] = useState<{title: string; content: string}[]>([]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, genStatus]);

  // Shared file upload logic (used by button, drag-drop, and paste)
  const uploadFile = async (file: File) => {
    setUploading(true);
    try {
      const data = await uploadProjectReference(file, projectId, taskId);
      // If canvas is managing references, notify parent to create a reference node.
      // Otherwise fall back to local reference state (Easy Mode / no canvas).
      if (onReferenceUploaded) {
        onReferenceUploaded(file.name, data.publicUrl);
      } else {
        setReferences((prev) => [...prev, { filename: file.name, url: data.publicUrl }]);
        // Auto-select newly uploaded reference
        setSelectedRefUrls((prev) => new Set([...prev, data.publicUrl]));
      }
      toast.success(`Reference "${file.name}" uploaded`);
    } catch (err) {
      console.error(err);
      toast.error("Failed to upload reference asset");
    } finally {
      setUploading(false);
    }
  };

  // Drag-and-drop handler for the input area
  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      await uploadFile(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  // Clipboard paste handler — intercepts Ctrl+V with image data
  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.items);
    const imageItem = items.find((item) => item.type.startsWith("image/"));
    if (imageItem) {
      e.preventDefault();
      const file = imageItem.getAsFile();
      if (file) {
        const namedFile = new File([file], `pasted-image-${Date.now()}.png`, { type: file.type });
        await uploadFile(namedFile);
      }
    }
  };

  // @-mention: show picker when user types @
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);
    // Auto-resize textarea height
    const textarea = e.target;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 128)}px`;
    // Show picker when last char typed is @ and there are references to pick from
    if (val.includes("@") && references.length > 0) {
      setShowAtPicker(true);
    } else {
      setShowAtPicker(false);
    }

    // Clear auto-suggestions when input changes (user is editing, not searching).
    if (autoSuggestions.length > 0) {
      setAutoSuggestions([]);
    }
  };

  const handleAtSelect = (ref: { filename: string; url: string }) => {
    // Replace the trailing @ with @filename
    setInput((prev) => prev.replace(/@$/, `@${ref.filename} `));
    setShowAtPicker(false);
    inputRef.current?.focus();
  };

  // Load prior chat history on task open/reopen (Req 11.5).
  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setHistoryError(false);
      try {
        const history = await getChatHistory(projectId, taskId);
        if (cancelled) return;

        if (history.length > 0) {
          setMessages(
            history.map((turn) => ({
              sender: turn.role === "assistant" ? "agent" : "user",
              text: turn.content,
              timestamp: turn.createdAt ? new Date(turn.createdAt) : new Date(),
            }))
          );
        } else {
          setMessages([WELCOME_MESSAGE]);
        }

        // Also load any previously-generated ads so the Output Gallery persists on refresh.
        const persistedAds = await getGeneratedAds(projectId, taskId);
        const hasFinalV3Video = persistedAds.some(
          (ad) => ad.mediaType === "video" && /\/final_video\.mp4(?:\?|$)/.test(ad.publicUrl ?? "")
        );
        if (!cancelled && persistedAds.length > 0) {
          setOutputs(persistedAds);

          // If canvas has no nodes but we have persisted ads, rebuild nodes from ads.
          // This handles the case where generation completed in the background after
          // the user navigated away (background task fix).
          const currentNodes = initialPipelineState?.nodes ?? [];
          if (currentNodes.length === 0 && persistedAds.length > 0) {
            const rebuiltNodes = persistedAds.map((ad, i) => ({
              id: `node-${ad.mediaType}-${ad.adId || i}`,
              type: ad.mediaType as NodeType,
              x: 100 + (i % 3) * 220,
              y: 100 + Math.floor(i / 3) * 200,
              label: `${ad.mediaType.charAt(0).toUpperCase() + ad.mediaType.slice(1)} Agent`,
              props: { compliance_status: ad.complianceStatus },
              status: "done" as const,
              output: ad.mediaType === "text" ? ad.caption : ad.publicUrl,
              error: null,
            }));
            const rebuiltPipeline: PipelineState = {
              nodes: rebuiltNodes,
              edges: [],
              viewport: { panX: 0, panY: 0, zoom: 1 },
            };
            onStateUpdate(rebuiltPipeline);
          }
        }

        // Restore a persisted video_plan (storyboard) if one exists in pipeline_state (B3).
        if (!cancelled && initialPipelineState && !hasFinalV3Video) {
          const rawPlan = (initialPipelineState as unknown as Record<string, unknown>).video_plan;
          if (rawPlan) {
            const restored = normalizeVideoPlan(rawPlan);
            // A restored plan should be available in Outputs without stealing focus
            // when the user intentionally switches back to Agent Chatbot.
            if (restored) setVideoPlan(restored, false);
          }
        }
      } catch (err) {
        if (cancelled) return;
        console.error(err);
        setHistoryError(true);
      }
    }

    loadHistory();
    return () => { cancelled = true; };
  }, [projectId, taskId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadFile(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input;
    // Canvas mode: use active reference node URLs from the canvas (persistent across sends).
    // Local mode (Easy / no canvas): use selected local reference uploads.
    const activeRefs = canvasReferenceUrls !== undefined
      ? canvasReferenceUrls
      : references.filter((r) => selectedRefUrls.has(r.url)).map((r) => r.url);
    const refUrls = Array.from(new Set([
      ...activeRefs,
      ...(revisionContext?.parentAssetUrl ? [revisionContext.parentAssetUrl] : []),
    ]));
    const resolvedPlatform: TargetPlatform = targetPlatform ?? DEFAULT_PLATFORM;

    setInput("");
    // In canvas mode, references live on the canvas — don't clear local state.
    if (canvasReferenceUrls === undefined) {
      setReferences([]);
      setSelectedRefUrls(new Set());
    }
    setStreamError(false);
    setGenStatus(null);
    // Don't clear videoPlan here — it will be cleared by the server when
    // the final pipeline_state arrives without video_plan (after rendering),
    // or replaced by a new plan event. This keeps the storyboard visible
    // during continuation commands like "continue" or "render it".
    setMessages((prev) => [
      ...prev,
      {
        sender: "user",
        text: userText + (refUrls.length > 0 ? `\n*(${refUrls.length} reference${refUrls.length > 1 ? "s" : ""} attached)*` : ""),
        timestamp: new Date(),
      },
    ]);
    setLoading(true);

    // Placeholder message for the streaming agent reply.
    setMessages((prev) => [...prev, { sender: "agent", text: "", timestamp: new Date() }]);

    let receivedFinalState = false;

    try {
      for await (const event of streamChat(
        projectId,
        taskId,
        userText,
        refUrls,
        resolvedPlatform,
        !complianceEnabled,
        targetEthnicity,
        { ...generationOptions, ...revisionContext }
      )) {
        if (typeof event.text === "string" && event.text.length > 0) {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.sender === "agent") {
              updated[updated.length - 1] = { ...last, text: last.text + event.text };
            }
            return updated;
          });
        }

        if (event.status) {
          const label = event.node ? `${event.node}: ${event.status}` : event.status;
          setGenStatus(label);
        }

        if (event.pipeline_state) {
          receivedFinalState = true;
          onStateUpdate(event.pipeline_state);
          setOutputs(mapGeneratedAds(event.pipeline_state));

          // If the returned pipeline_state no longer contains a video_plan,
          // clear the local storyboard (e.g. after successful video render).
          const returnedPlan = (event.pipeline_state as unknown as Record<string, unknown>).video_plan;
          if (!returnedPlan) {
            setVideoPlan(null);
          }
        }

        if (event.video_plan) {
          const plan = normalizeVideoPlan(event.video_plan);
          if (plan) {
            setVideoPlan(plan);
            receivedFinalState = true; // a plan is a valid end-of-stream result
          }
        }

        if (event.error) {
          toast.error(`Agent generation error: ${event.error}`);
        }
      }

      if (receivedFinalState) {
        setGenStatus(null);
        toast.success("Ad generation stream completed successfully!");
      } else {
        setStreamError(true);
        toast.error("Generation did not complete — the stream ended early.");
      }
    } catch (err) {
      console.error(err);
      setStreamError(true);
      toast.error("Failed to generate ad assets");
    } finally {
      if (revisionContext) onRevisionContextUsed?.();
      setLoading(false);
    }
  };



  return (
    <div className="flex h-full flex-col bg-card text-foreground">
      {/* Chat history load-error indication (Req 11.6) */}
      {historyError && (
        <div className="flex items-center gap-2 border-b bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertTriangle size={14} className="shrink-0" />
          <span>Could not load prior chat history. You can still start a new conversation.</span>
        </div>
      )}

      {/* Chat Messages Log */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-2.5 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.sender === "agent" && (
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-primary/10 text-primary">
                <Bot size={16} />
              </div>
            )}
            <div
              className={`rounded-lg px-3 py-2 text-sm shadow-sm max-w-[85%] border leading-relaxed ${
                msg.sender === "user"
                  ? "bg-primary text-primary-foreground border-primary font-medium"
                  : "bg-muted text-foreground border-border"
              }`}
            >
              {msg.sender === "agent" ? renderMarkdown(msg.text) : msg.text}
            </div>
            {msg.sender === "user" && (
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-secondary/80 text-foreground border">
                <User size={16} />
              </div>
            )}
          </div>
        ))}

        {/* Live generation status (Req 10.2) */}
        {loading && genStatus && (
          <div className="flex items-start gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary animate-bounce">
              <Bot size={16} />
            </div>
            <div className="rounded-lg bg-muted border px-4 py-2.5 text-xs text-muted-foreground flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-ping" />
              <span>{genStatus}</span>
            </div>
          </div>
        )}

        {loading && !genStatus && messages[messages.length - 1]?.text === "" && (
          <div className="flex items-start gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary animate-bounce">
              <Bot size={16} />
            </div>
            <div className="rounded-lg bg-muted border px-4 py-2.5 text-xs text-muted-foreground flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-ping" />
              <span>Agent is connecting to Google Gemini model...</span>
            </div>
          </div>
        )}

        {/* Stream-ended-early error indication (Req 10.7) */}
        {streamError && (
          <div className="flex items-start gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
              <AlertTriangle size={16} />
            </div>
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-xs text-destructive">
              Generation did not complete. The stream ended before a final result. Any content shown above is preserved.
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box Footer — drag-drop zone + image thumbnails + text input */}
      <div
        className="border-t p-3 bg-card flex flex-col gap-2"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {/* Starter suggestion chips — shown only when no user messages exist */}
        {messages.length <= 1 && !loading && (
          <div className="flex flex-wrap gap-1.5 mb-1">
            {[
              "Create a TikTok video ad for my product",
              "I need an Instagram post for a sale",
              "Make a Shopee product showcase video",
              "Help me — what info do you need?",
            ].map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => {
                  setInput(suggestion);
                  inputRef.current?.focus();
                }}
                className="rounded-full border border-border bg-muted/50 px-3 py-1.5 text-[11px] text-muted-foreground hover:bg-primary/10 hover:text-primary hover:border-primary/30 transition-colors cursor-pointer"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        {/* Reference indicator — canvas mode shows live node status, local mode shows thumbnails */}
        {canvasReferenceUrls !== undefined ? (
          /* Canvas mode: show how many reference nodes are active */
          canvasReferenceUrls.length > 0 ? (
            <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-md bg-sky-500/10 border border-sky-500/20">
              <CheckCircle2 size={12} className="text-sky-500 shrink-0" />
              <span className="text-[10px] text-sky-700 dark:text-sky-400 font-medium">
                {canvasReferenceUrls.length} reference{canvasReferenceUrls.length > 1 ? "s" : ""} active
              </span>
              <span className="text-[10px] text-muted-foreground ml-auto">Click nodes on canvas to toggle</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-md bg-muted/40 border border-border/40">
              <Circle size={12} className="text-muted-foreground shrink-0" />
              <span className="text-[10px] text-muted-foreground">
                No references active — upload or click nodes on canvas to include
              </span>
            </div>
          )
        ) : (
          /* Local mode (Easy Mode): selectable thumbnail grid */
          references.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {references.map((ref, idx) => {
                const isImage = /\.(jpg|jpeg|png|gif|webp|svg|bmp)$/i.test(ref.filename);
                const isSelected = selectedRefUrls.has(ref.url);
                return (
                  <div
                    key={idx}
                    className={`relative group rounded-lg border-2 overflow-hidden cursor-pointer transition-all duration-150 ${
                      isSelected
                        ? "border-primary shadow-[0_0_0_1px_hsl(var(--primary)/0.3)]"
                        : "border-border opacity-50 hover:opacity-75"
                    }`}
                    onClick={() => toggleRefSelection(ref.url)}
                    title={isSelected ? `${ref.filename} — click to exclude` : `${ref.filename} — click to include`}
                    role="checkbox"
                    aria-checked={isSelected}
                    aria-label={`${ref.filename} reference ${isSelected ? "selected" : "deselected"}`}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggleRefSelection(ref.url); }
                    }}
                  >
                    {isImage ? (
                      <img src={ref.url} alt={ref.filename} className="h-20 w-20 object-cover" />
                    ) : (
                      <div className="flex h-20 w-20 flex-col items-center justify-center gap-1 p-2 bg-muted/50">
                        <FileCheck size={20} className="text-muted-foreground" />
                        <span className="text-[9px] text-muted-foreground truncate w-full text-center">{ref.filename}</span>
                      </div>
                    )}
                    <div className="absolute top-1 left-1 pointer-events-none">
                      {isSelected
                        ? <CheckCircle2 size={15} className="text-primary drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]" />
                        : <Circle size={15} className="text-white/80 drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]" />}
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedRefUrls((prev) => { const next = new Set(prev); next.delete(ref.url); return next; });
                        setReferences((prev) => prev.filter((_, i) => i !== idx));
                      }}
                      className="absolute top-1 right-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                      title={`Remove ${ref.filename}`}
                      aria-label={`Remove ${ref.filename}`}
                    >
                      <span className="text-xs font-bold leading-none">×</span>
                    </button>
                  </div>
                );
              })}
            </div>
          )
        )}

        {/* @-mention picker dropdown */}
        {showAtPicker && references.length > 0 && (
          <div className="rounded-md border bg-background shadow-md p-1 max-h-32 overflow-y-auto">
            <p className="px-2 py-1 text-[10px] text-muted-foreground font-semibold">Reference files:</p>
            {references.map((ref, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleAtSelect(ref)}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-foreground hover:bg-muted transition-colors cursor-pointer"
              >
                <FileCheck size={12} className="text-primary shrink-0" />
                <span className="truncate">{ref.filename}</span>
              </button>
            ))}
          </div>
        )}

        {/* Prompt search (vector DB) — click sparkles, type, press Enter to search */}
        {showPromptSearch && (
          <div className="rounded-lg border bg-muted/20 p-2">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Type what you want to create, then press Enter..."
                className="flex-1 rounded-md border bg-background px-3 py-2 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                onKeyDown={async (e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    const query = (e.target as HTMLInputElement).value.trim();
                    if (!query) return;
                    try {
                      setAutoSuggestions((await searchPromptLibrary(query, 5)).slice(0, 5));
                    } catch { /* silent */ }
                  }
                }}
              />
            </div>
            {autoSuggestions.length > 0 && (
              <div className="mt-2 flex flex-col gap-1 max-h-40 overflow-y-auto">
                {autoSuggestions.map((s, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInput(s.content || s.title);
                      setAutoSuggestions([]);
                      setShowPromptSearch(false);
                      inputRef.current?.focus();
                    }}
                    className="flex w-full flex-col gap-0.5 rounded px-2 py-1.5 text-left hover:bg-muted transition-colors cursor-pointer"
                  >
                    <span className="text-[10px] font-semibold text-foreground line-clamp-1">{s.title}</span>
                    <span className="text-[9px] text-muted-foreground line-clamp-1">{(s.content || "").slice(0, 80)}...</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSend} className="flex gap-2">
          <button
            type="button"
            disabled={loading || uploading}
            onClick={() => setShowPromptSearch((v) => !v)}
            className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-muted disabled:opacity-50 transition-colors cursor-pointer ${showPromptSearch ? "text-primary border-primary" : ""}`}
            title="Search prompt templates"
            aria-label="Find an ad idea"
          >
            <Sparkles size={16} className={showPromptSearch ? "text-primary" : "text-muted-foreground"} />
          </button>

          <label
            className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-muted transition-colors cursor-pointer ${loading || uploading ? "opacity-50 pointer-events-none" : ""}`}
            title="Upload reference files (images/video)"
            aria-label="Upload a product photo or reference file"
          >
            {uploading ? (
              <Loader2 size={16} className="animate-spin text-muted-foreground" />
            ) : (
              <Paperclip size={16} className="text-muted-foreground" />
            )}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept="image/*,video/*,audio/*,.txt,.pdf"
              multiple
            />
          </label>

          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onPaste={handlePaste}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (input.trim() && !loading && !uploading) {
                  handleSend(e as unknown as React.FormEvent);
                }
              }
            }}
            placeholder={uploading ? "Uploading file..." : "Describe the ad you want..."}
            aria-label="Describe the ad you want"
            disabled={loading || uploading}
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 max-h-32 overflow-y-auto"
            style={{ minHeight: "36px" }}
          />
          <button
            type="submit"
            disabled={loading || uploading || !input.trim()}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary/95 disabled:opacity-50 transition-colors cursor-pointer"
            aria-label="Send message"
          >
            <Send size={16} />
          </button>
        </form>

        <p className="text-[10px] text-muted-foreground text-center">
          Add a product photo for a more accurate result.
        </p>
      </div>
    </div>
  );
}

export default ChatbotPanel;
