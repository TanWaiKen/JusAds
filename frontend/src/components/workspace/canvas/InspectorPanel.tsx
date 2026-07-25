/**
 * InspectorPanel — right panel showing the selected node's editable properties and output.
 * Label and custom props can be edited inline and dispatch UPDATE_NODE_PROPS.
 * For "input" nodes the reference_urls prop renders as a polished upload/remove editor
 * instead of a raw text field.
 */

import { useState, useEffect } from "react";
import { Upload, X, ImageIcon, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { API_BASE } from "@/services/taskApi";
import type { CanvasNode } from "@/components/workspace/canvas/graphModel";

interface InspectorPanelProps {
  node: CanvasNode | null;
  projectId?: string;
  taskId?: string;
  onUpdateProps?: (nodeId: string, updates: { label?: string; props?: Record<string, string> }) => void;
  onDelete?: (nodeId: string) => void;
  onSendRevision?: (node: CanvasNode, comment: string) => void;
  /** Callback to re-render only the video step using the existing upstream assets. */
  onRerender?: (node: CanvasNode) => void;
  /** True while a re-render is in progress. */
  isRerendering?: boolean;
}

// ─── Reference URL editor for the "input" node ───────────────────────────────

interface ReferenceUrlsEditorProps {
  nodeId: string;
  projectId: string;
  taskId: string;
  /** Current reference_urls prop value — may be a comma-string or an array from the backend */
  value: string | string[];
  onChange: (newValue: string) => void;
}

/**
 * Renders each reference URL as a thumbnail card with a remove button.
 * An upload button uploads to S3 via the task upload endpoint and appends the URL.
 */
function ReferenceUrlsEditor({ nodeId, projectId, taskId, value, onChange }: ReferenceUrlsEditorProps) {
  // value may be a comma-string or an actual array coming from the backend prop
  const urls = Array.isArray(value)
    ? (value as unknown as string[]).filter(Boolean)
    : String(value).split(",").map((u) => u.trim()).filter(Boolean);

  const [uploading, setUploading] = useState(false);

  const handleRemove = (urlToRemove: string) => {
    const next = urls.filter((u) => u !== urlToRemove).join(",");
    onChange(next);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(
        `${API_BASE}/api/projects/${projectId}/tasks/${taskId}/upload`,
        { method: "POST", body: formData }
      );
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json() as { public_url: string };
      const next = [...urls, data.public_url].join(",");
      onChange(next);
      toast.success(`Reference "${file.name}" added`);
    } catch {
      toast.error("Failed to upload reference");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const isImage = (url: string) =>
    /\.(jpg|jpeg|png|gif|webp|svg|bmp)/i.test(url.split("?")[0]);

  return (
    <div className="space-y-2">
      {/* Existing reference thumbnails */}
      {urls.length === 0 && (
        <p className="text-[10px] text-muted-foreground italic">No references attached.</p>
      )}
      <div className="flex flex-wrap gap-2">
        {urls.map((url, i) => (
          <div key={url} className="relative group rounded-md border border-border overflow-hidden w-[72px] h-[72px] bg-muted shrink-0">
            {isImage(url) ? (
              <img src={url} alt={`Ref ${i + 1}`} className="w-full h-full object-cover" />
            ) : (
              <div className="flex flex-col items-center justify-center w-full h-full">
                <ImageIcon size={20} className="text-muted-foreground" />
                <span className="text-[8px] text-muted-foreground mt-1 px-1 text-center leading-tight truncate w-full">{url.split("/").pop()}</span>
              </div>
            )}
            {/* Remove button */}
            <button
              onClick={() => handleRemove(url)}
              className="absolute top-0.5 right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-black/70 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              aria-label="Remove reference"
            >
              <X size={8} />
            </button>
            {/* Index badge */}
            <div className="absolute bottom-0.5 left-0.5 rounded bg-black/60 px-1 py-px text-[8px] text-white font-medium">
              {i + 1}
            </div>
          </div>
        ))}

        {/* Upload tile — label wraps the input so click is always a trusted gesture */}
        <label
          className={`flex flex-col items-center justify-center w-[72px] h-[72px] rounded-md border-2 border-dashed border-border hover:border-primary hover:bg-primary/5 transition-colors text-muted-foreground hover:text-primary shrink-0 ${uploading ? "opacity-50 pointer-events-none" : "cursor-pointer"}`}
          aria-label="Upload new reference"
          title="Upload new reference image"
        >
          {uploading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <>
              <Upload size={18} />
              <span className="text-[9px] mt-1 font-medium">Upload</span>
            </>
          )}
          <input
            type="file"
            accept="image/*,video/*"
            className="hidden"
            onChange={handleUpload}
          />
        </label>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

interface ParsedScene {
  index: string;
  duration: string;
  visual: string;
  voiceover: string;
  subtitle: string;
}

function parseDirectorPrompt(prompt: string): ParsedScene[] {
  const blocks = prompt.split("\n\n").filter(Boolean);
  return blocks.map((block) => {
    const lines = block.split("\n").map((l) => l.trim());
    const header = lines[0] || ""; // e.g. "Scene 1 — 5s"
    const matchHeader = header.match(/Scene\s+(\d+)\s*(?:—\s*(.*))?/i);
    const index = matchHeader ? matchHeader[1] : "?";
    const duration = matchHeader && matchHeader[2] ? matchHeader[2] : "";

    const visual = lines.find((l) => l.startsWith("Visual:"))?.replace("Visual:", "").trim() || "";
    const voiceover = lines.find((l) => l.startsWith("Voice-over:"))?.replace("Voice-over:", "").trim() || "";
    const subtitle = lines.find((l) => l.startsWith("On-screen text:"))?.replace("On-screen text:", "").trim() || "";

    return { index, duration, visual, voiceover, subtitle };
  });
}

export function InspectorPanel({ node, projectId, taskId, onUpdateProps, onDelete, onSendRevision, onRerender, isRerendering }: InspectorPanelProps) {
  const [editLabel, setEditLabel] = useState("");
  const [editProps, setEditProps] = useState<Record<string, string>>({});
  const [revisionComment, setRevisionComment] = useState("");
  const [showRawPrompt, setShowRawPrompt] = useState(false);

  const handleSendRevision = () => {
    if (onSendRevision && node && revisionComment.trim()) {
      onSendRevision(node, revisionComment.trim());
      setRevisionComment("");
    }
  };

  // Sync local state when node changes
  useEffect(() => {
    if (node) {
      setEditLabel(node.label);
      // Normalize any array prop values to comma-strings so editProps stays Record<string,string>
      const normalized: Record<string, string> = {};
      for (const [k, v] of Object.entries(node.props)) {
        normalized[k] = Array.isArray(v) ? (v as string[]).join(",") : String(v ?? "");
      }
      setEditProps(normalized);
      setShowRawPrompt(false);
    }
  }, [node]);

  if (!node) {
    return (
      <div className="w-full p-4">
        <p className="text-sm text-muted-foreground">Select a node to inspect its properties</p>
      </div>
    );
  }

  function handleLabelBlur() {
    if (node && editLabel !== node.label && onUpdateProps) {
      onUpdateProps(node.id, { label: editLabel });
    }
  }

  function handlePropChange(key: string, value: string) {
    setEditProps((prev) => ({ ...prev, [key]: value }));
  }

  function handlePropBlur(key: string) {
    if (node && editProps[key] !== node.props[key] && onUpdateProps) {
      onUpdateProps(node.id, { props: { [key]: editProps[key] } });
    }
  }

  return (
    <div className="w-full h-full overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground">Inspector</h3>
        {onDelete && (
          <button
            onClick={() => onDelete(node.id)}
            className="text-xs text-muted-foreground hover:text-destructive transition-colors"
          >
            Delete
          </button>
        )}
      </div>

      {/* Node info — editable label */}
      <div className="mb-4 space-y-3">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Label</label>
          <input
            type="text"
            value={editLabel}
            onChange={(e) => setEditLabel(e.target.value)}
            onBlur={handleLabelBlur}
            onKeyDown={(e) => { if (e.key === "Enter") handleLabelBlur(); }}
            className="w-full rounded-md border bg-background px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Type</label>
          <p className="text-sm text-foreground capitalize">{node.type}</p>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Status</label>
          <p className="text-sm text-foreground capitalize">{node.status}</p>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Position</label>
          <p className="text-sm text-foreground">
            ({Math.round(node.x)}, {Math.round(node.y)})
          </p>
        </div>
      </div>

      {/* Properties — editable */}
      {Object.keys(editProps).length > 0 && (
        <div className="mb-4">
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">Properties</h4>
          <div className="space-y-3">
            {Object.entries(editProps).map(([key, value]) => {
              if (key === "prompt_used" && node.type === "orchestrator") {
                const parsedScenes = parseDirectorPrompt(value || "");
                return (
                  <div key={key} className="flex flex-col gap-2 border-t pt-3 mt-3 border-border">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Script Details</span>
                      <button
                        type="button"
                        onClick={() => setShowRawPrompt(!showRawPrompt)}
                        className="text-[10px] font-semibold text-primary hover:underline cursor-pointer"
                      >
                        {showRawPrompt ? "View Beautiful Table" : "Edit Raw Script Text"}
                      </button>
                    </div>
                    {showRawPrompt ? (
                      <textarea
                        value={value}
                        onChange={(e) => handlePropChange(key, e.target.value)}
                        onBlur={() => handlePropBlur(key)}
                        className="w-full text-xs font-mono p-2.5 rounded-md border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary min-h-[260px] leading-normal"
                        placeholder="Scene 1 — 5s&#10;Visual: ...&#10;Voice-over: ...&#10;On-screen text: ..."
                      />
                    ) : (
                      <div className="overflow-x-auto border border-border rounded-lg bg-card shadow-sm max-w-full">
                        <table className="min-w-full divide-y divide-border text-[11px]">
                          <thead className="bg-muted/65">
                            <tr>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground w-12">Scene</th>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground min-w-[130px]">Visual Description</th>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground min-w-[110px]">Voiceover (TTS)</th>
                              <th className="px-2.5 py-2 text-left font-bold text-muted-foreground min-w-[100px]">On-Screen Text</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border bg-background">
                            {parsedScenes.map((s, idx) => (
                              <tr key={idx} className="hover:bg-muted/10 transition-colors">
                                <td className="px-2.5 py-2 font-bold text-primary align-top">
                                  {s.index}
                                  {s.duration && <span className="block text-[9px] font-normal text-muted-foreground mt-0.5">{s.duration}</span>}
                                </td>
                                <td className="px-2.5 py-2 text-foreground leading-relaxed align-top whitespace-pre-wrap">{s.visual}</td>
                                <td className="px-2.5 py-2 text-foreground leading-relaxed align-top whitespace-pre-wrap">{s.voiceover}</td>
                                <td className="px-2.5 py-2 text-foreground leading-relaxed align-top whitespace-pre-wrap">{s.subtitle}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              }

              return (
                <div key={key}>
                  <label className="text-xs text-muted-foreground block mb-0.5">{key}</label>
                  {key === "reference_urls" && node.type === "input" && projectId && taskId ? (
                    <ReferenceUrlsEditor
                      nodeId={node.id}
                      projectId={projectId}
                      taskId={taskId}
                      value={value}
                      onChange={(newValue) => {
                        handlePropChange(key, newValue);
                        if (onUpdateProps) onUpdateProps(node.id, { props: { [key]: newValue } });
                      }}
                    />
                  ) : (
                    <input
                      type="text"
                      value={value}
                      onChange={(e) => handlePropChange(key, e.target.value)}
                      onBlur={() => handlePropBlur(key)}
                      onKeyDown={(e) => { if (e.key === "Enter") handlePropBlur(key); }}
                      className="w-full rounded-md border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Output (with media preview) */}
      {node.output && (
        <div className="mb-4">
          <h4 className="mb-1 text-xs font-medium text-muted-foreground">Output Preview</h4>
          <div className="rounded-md bg-muted/50 p-2">
            {node.type === "image" && (node.output.startsWith("/") || node.output.startsWith("http")) ? (
              <img src={node.output} className="w-full max-h-[200px] object-contain rounded border bg-black/10 dark:bg-white/5" alt={node.label} />
            ) : node.type === "audio" && (node.output.startsWith("/") || node.output.startsWith("http")) ? (
              <audio src={node.output} controls className="w-full" />
            ) : node.type === "video" && (node.output.startsWith("/") || node.output.startsWith("http")) ? (
              <video src={node.output} controls className="w-full max-h-[200px] rounded border" />
            ) : (
              <p className="text-xs text-foreground whitespace-pre-wrap break-all">{node.output}</p>
            )}
          </div>
          
          {/* Revision request input */}
          <div className="mt-4 pt-4 border-t border-border">
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">Request Revision / Feedback</h4>
            <textarea
              value={revisionComment}
              onChange={(e) => setRevisionComment(e.target.value)}
              placeholder={`Suggest edits for this ${node.type} node (e.g. "make the background brighter", "use a deeper voice")...`}
              className="w-full text-xs p-2 rounded border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary min-h-[60px]"
            />
            <button
              onClick={handleSendRevision}
              disabled={!revisionComment.trim()}
              className="mt-2 w-full inline-flex items-center justify-center gap-1.5 rounded bg-primary py-1.5 text-xs font-semibold text-primary-foreground disabled:opacity-40 hover:bg-primary/90 transition-colors cursor-pointer"
            >
              Send Revision to Agent
            </button>
          </div>
        </div>
      )}

      {/* Re-render Video button — only for V3 video nodes */}
      {node.type === "video" && node.props.pipeline === "v3_grid" && onRerender && (
        <div className="mb-4 pt-3 border-t border-border">
          <button
            onClick={() => onRerender(node)}
            disabled={isRerendering}
            className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-black px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-black/80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRerendering ? "Re-rendering…" : "Re-render Video"}
          </button>
          <p className="mt-1.5 text-[10px] text-muted-foreground leading-tight">
            Re-runs only the video generation using the existing Scene Grid, Character Sheet, and frame references. Upstream nodes are not affected.
          </p>
        </div>
      )}

      {/* Error */}
      {node.error && (
        <div className="mb-4">
          <h4 className="mb-1 text-xs font-medium text-red-500">Error</h4>
          <div className="rounded-md bg-red-500/10 p-2">
            <p className="text-xs text-red-600 dark:text-red-400 whitespace-pre-wrap">{node.error}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default InspectorPanel;
