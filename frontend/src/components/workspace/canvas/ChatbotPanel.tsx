import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { API_BASE } from "@/services/taskApi";
import { consumePrefill } from "@/services/session";
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
} from "@/services/generationApi";
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
  videoV3Enabled: boolean;
  targetEthnicity: TargetEthnicity;
  generationOptions: GenerationOptions;
  initialPipelineState?: PipelineState;
  onOutputsUpdate?: (ads: GeneratedAdView[]) => void;
  onVideoPlanUpdate?: (plan: VideoPlan | null) => void;
  triggerPrompt?: string | null;
  onTriggerPromptUsed?: () => void;
  revisionContext?: Pick<GenerationOptions, "parentAdId" | "parentAssetUrl"> | null;
  onRevisionContextUsed?: () => void;
}

const WELCOME_MESSAGE: Message = {
  sender: "agent",
  text: "Hello! I am your AI Ad Generation Agent chatbot. 🤖\n\nI can generate text copy, image banners, voiceover audio, or video ads for you! Just tell me what you want to create (e.g. *'Generate a TikTok video and text caption ad for a sports watch'*), and I will build the node pipeline on the canvas and run the local generator tools for you.\n\nYou can also upload reference assets below for me to read!",
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

/** Lightweight Markdown-to-HTML renderer for agent messages. */
function renderMarkdown(text: string) {
  if (!text) return "";

  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

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
  videoV3Enabled,
  targetEthnicity,
  generationOptions,
  initialPipelineState,
  onOutputsUpdate,
  onVideoPlanUpdate,
  triggerPrompt,
  onTriggerPromptUsed,
  revisionContext,
  onRevisionContextUsed,
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
  const [uploading, setUploading] = useState(false);
  const [genStatus, setGenStatus] = useState<string | null>(null);
  const [streamError, setStreamError] = useState(false);
  const [historyError, setHistoryError] = useState(false);

  // Wrapped setters that also notify the parent (lifted state for Outputs tab).
  const setOutputs = (ads: GeneratedAdView[]): void => {
    onOutputsUpdate?.(ads);
  };
  const setVideoPlan = (plan: VideoPlan | null): void => {
    onVideoPlanUpdate?.(plan);
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
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(
        `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/upload`,
        { method: "POST", body: formData }
      );

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();
      setReferences((prev) => [...prev, { filename: file.name, url: data.public_url }]);
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
        if (!cancelled && initialPipelineState) {
          const rawPlan = (initialPipelineState as unknown as Record<string, unknown>).video_plan;
          if (rawPlan) {
            const restored = normalizeVideoPlan(rawPlan);
            if (restored) setVideoPlan(restored);
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
    const refUrls = Array.from(new Set([
      ...references.map((r) => r.url),
      ...(revisionContext?.parentAssetUrl ? [revisionContext.parentAssetUrl] : []),
    ]));
    const resolvedPlatform: TargetPlatform = targetPlatform ?? DEFAULT_PLATFORM;

    setInput("");
    setReferences([]);
    setStreamError(false);
    setGenStatus(null);
    setVideoPlan(null);
    setMessages((prev) => [
      ...prev,
      {
        sender: "user",
        text: userText + (refUrls.length > 0 ? `\n*(Uploaded references: ${refUrls.length} files)*` : ""),
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
        videoV3Enabled,
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
        {/* Uploaded reference thumbnails */}
        {references.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {references.map((ref, idx) => {
              const isImage = /\.(jpg|jpeg|png|gif|webp|svg|bmp)$/i.test(ref.filename);
              return (
                <div
                  key={idx}
                  className="relative group rounded-lg border bg-muted/50 overflow-hidden"
                >
                  {isImage ? (
                    <img
                      src={ref.url}
                      alt={ref.filename}
                      className="h-20 w-20 object-cover rounded-lg"
                    />
                  ) : (
                    <div className="flex h-20 w-20 flex-col items-center justify-center gap-1 p-2">
                      <FileCheck size={20} className="text-muted-foreground" />
                      <span className="text-[9px] text-muted-foreground truncate w-full text-center">
                        {ref.filename}
                      </span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => setReferences((prev) => prev.filter((_, i) => i !== idx))}
                    className="absolute top-1 right-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                    title={`Remove ${ref.filename}`}
                  >
                    <span className="text-xs font-bold">×</span>
                  </button>
                </div>
              );
            })}
          </div>
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
                      const res = await fetch(
                        `${API_BASE}/api/prompt-suggestions?query=${encodeURIComponent(query)}&top_k=5`
                      );
                      if (res.ok) {
                        const data = (await res.json()) as { suggestions?: { title: string; content: string }[] };
                        setAutoSuggestions((data.suggestions || []).slice(0, 5));
                      }
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
            className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-muted disabled:opacity-50 transition-colors cursor-pointer ${showPromptSearch ? "text-primary border-primary" : ""}`}
            title="Search prompt templates"
          >
            <Sparkles size={16} className={showPromptSearch ? "text-primary" : "text-muted-foreground"} />
          </button>

          <button
            type="button"
            disabled={loading || uploading}
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-input bg-background hover:bg-muted disabled:opacity-50 transition-colors cursor-pointer"
            title="Upload reference files (images/video)"
          >
            {uploading ? (
              <Loader2 size={16} className="animate-spin text-muted-foreground" />
            ) : (
              <Paperclip size={16} className="text-muted-foreground" />
            )}
          </button>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="hidden"
            accept="image/*,video/*,audio/*,.txt,.pdf"
            multiple
          />

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
            placeholder={uploading ? "Uploading file..." : "Ask Anything...."}
            disabled={loading || uploading}
            rows={1}
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 max-h-32 overflow-y-auto"
            style={{ minHeight: "36px" }}
          />
          <button
            type="submit"
            disabled={loading || uploading || !input.trim()}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary/95 disabled:opacity-50 transition-colors cursor-pointer"
          >
            <Send size={16} />
          </button>
        </form>

        <p className="text-[10px] text-muted-foreground text-center">
          Drop files here, paste images (Ctrl+V), or type @ to reference uploaded files
        </p>
      </div>
    </div>
  );
}

export default ChatbotPanel;
