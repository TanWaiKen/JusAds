/**
 * CanvasNode — a single node on the Generation Canvas.
 * Displays type color, label, input/output ports, status indicator, and selection ring.
 */

import { useState } from "react";
import { Trash2, Download, Eye, X } from "lucide-react";
import type { CanvasNode as CanvasNodeType, NodeStatus, NodeType } from "@/components/workspace/canvas/graphModel";

interface CanvasNodeProps {
  node: CanvasNodeType;
  isSelected: boolean;
  onSelect: (nodeId: string) => void;
  onDelete: (nodeId: string) => void;
  onDragStart: (nodeId: string, e: React.MouseEvent) => void;
  onResizeStart: (nodeId: string, e: React.MouseEvent) => void;
  onPortDragStart: (nodeId: string, portType: "output") => void;
  onPortDrop: (nodeId: string, portType: "input") => void;
  onContextMenu: (nodeId: string, e: React.MouseEvent) => void;
}

/** Node types that support asset download. */
const DOWNLOADABLE_TYPES: ReadonlySet<NodeType> = new Set(["image", "video", "audio"]);

/** Default file extensions per media type. */
const DEFAULT_EXTENSIONS: Record<string, string> = {
  image: "png",
  video: "mp4",
  audio: "mp3",
};

/**
 * Extracts a file extension from a URL path, falling back to the default for the node type.
 */
function getExtensionFromUrl(url: string, nodeType: string): string {
  try {
    const pathname = new URL(url).pathname;
    const lastDot = pathname.lastIndexOf(".");
    if (lastDot !== -1) {
      const ext = pathname.slice(lastDot + 1).toLowerCase();
      // Only accept reasonable extensions (2-5 chars, no query params)
      if (ext.length >= 2 && ext.length <= 5 && /^[a-z0-9]+$/.test(ext)) {
        return ext;
      }
    }
  } catch {
    // URL parsing failed — use default
  }
  return DEFAULT_EXTENSIONS[nodeType] ?? "bin";
}

/**
 * Triggers a browser download for the given asset URL.
 */
function handleAssetDownload(node: CanvasNodeType): void {
  if (!node.output) return;
  const extension = getExtensionFromUrl(node.output, node.type);
  const shortId = node.id.slice(-6);
  const filename = `${node.type}_${shortId}.${extension}`;

  const anchor = document.createElement("a");
  anchor.href = node.output;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
}

const NODE_COLORS: Record<string, string> = {
  orchestrator: "bg-purple-500",
  text: "bg-blue-500",
  image: "bg-green-500",
  audio: "bg-orange-500",
  video: "bg-red-500",
  critic: "bg-yellow-500",
  input: "bg-slate-500",
  output: "bg-emerald-500",
};

const STATUS_INDICATORS: Record<NodeStatus, string> = {
  idle: "bg-gray-400",
  running: "bg-blue-500 animate-pulse",
  done: "bg-green-500",
  error: "bg-red-500",
};

export function CanvasNode({
  node,
  isSelected,
  onSelect,
  onDelete,
  onDragStart,
  onResizeStart,
  onPortDragStart,
  onPortDrop,
  onContextMenu,
}: CanvasNodeProps) {
  const [showPreview, setShowPreview] = useState(false);
  const colorClass = NODE_COLORS[node.type] ?? "bg-gray-500";
  const statusClass = STATUS_INDICATORS[node.status];
  const isDownloadable = node.status === "done" && DOWNLOADABLE_TYPES.has(node.type as NodeType) && !!node.output;

  // Parse output JSON for output node summaries
  let parsedCampaignOutput: Record<string, string> | null = null;
  if (node.type === "output" && node.output) {
    try {
      parsedCampaignOutput = JSON.parse(node.output);
    } catch {
      // not json
    }
  }

  // Use node.width if set (user resized), otherwise compute default
  const defaultWidth = node.output && (node.type === "image" || node.type === "video" || node.type === "output" || node.type === "text") ? 220 : 180;
  const nodeWidth = node.width ?? defaultWidth;

  return (
    <div
      className={`absolute select-none rounded-lg border bg-card shadow-md transition-all ${
        isSelected ? "ring-2 ring-primary shadow-lg z-10" : "hover:shadow-lg"
      }`}
      style={{ left: node.x, top: node.y, width: nodeWidth, ...(node.height ? { minHeight: node.height } : {}) }}
      onMouseDown={(e) => {
        e.stopPropagation();
        onSelect(node.id);
        onDragStart(node.id, e);
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onContextMenu(node.id, e);
      }}
    >
      {/* Header */}
      <div className={`flex items-center gap-2 rounded-t-lg px-3 py-2 ${colorClass}`}>
        <span className="text-xs font-semibold text-white truncate">{node.label}</span>
        {isDownloadable && (
          <button
            onClick={(e) => { e.stopPropagation(); setShowPreview(true); }}
            className="ml-auto p-0.5 rounded text-white/60 hover:text-white hover:bg-white/20 transition-colors"
            aria-label="Preview asset"
            title="Preview"
          >
            <Eye size={12} />
          </button>
        )}
        {isDownloadable && (
          <button
            onClick={(e) => { e.stopPropagation(); handleAssetDownload(node); }}
            className="p-0.5 rounded text-white/60 hover:text-white hover:bg-white/20 transition-colors"
            aria-label="Download asset"
            title="Download"
          >
            <Download size={12} />
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(node.id); }}
          className={`${isDownloadable ? "" : "ml-auto "}p-0.5 rounded text-white/60 hover:text-white hover:bg-white/20 transition-colors`}
          aria-label="Delete node"
        >
          <Trash2 size={12} />
        </button>
        <div className={`h-2.5 w-2.5 rounded-full ${statusClass}`} />
      </div>

      {/* Body with ports */}
      <div className="relative flex items-center justify-between px-1 py-2">
        {/* Input port */}
        <div
          className="flex h-4 w-4 cursor-crosshair items-center justify-center rounded-full border-2 border-muted-foreground/40 bg-background hover:border-primary"
          onMouseUp={(e) => {
            e.stopPropagation();
            onPortDrop(node.id, "input");
          }}
          aria-label="Input port"
        >
          <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
        </div>

        <span className="text-[10px] font-mono text-muted-foreground uppercase">{node.type}</span>

        {/* Output port */}
        <div
          className="flex h-4 w-4 cursor-crosshair items-center justify-center rounded-full border-2 border-muted-foreground/40 bg-background hover:border-primary"
          onMouseDown={(e) => {
            e.stopPropagation();
            onPortDragStart(node.id, "output");
          }}
          aria-label="Output port"
        >
          <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
        </div>
      </div>

      {/* Dynamic Generated Asset Preview */}
      {node.output && (
        <div className="border-t border-border bg-muted/20 px-3 py-2 text-xs">
          {node.type === "text" && (
            <div className="max-h-24 overflow-y-auto whitespace-pre-wrap text-[10px] text-muted-foreground bg-background p-1.5 rounded border leading-tight">
              {node.output}
            </div>
          )}
          {node.type === "image" && (
            <div className="group cursor-pointer" onClick={(e) => { e.stopPropagation(); setShowPreview(true); }}>
              <img
                src={node.output}
                alt="Generated Ad"
                className="mt-1 max-h-32 w-full rounded border object-contain bg-background shadow-inner group-hover:opacity-80 transition-opacity"
              />
              <span className="text-[9px] text-muted-foreground group-hover:text-primary transition-colors mt-0.5 block">Click to preview</span>
            </div>
          )}
          {node.type === "audio" && (
            <audio
              src={node.output}
              controls
              className="mt-1 w-full scale-90 origin-left"
            />
          )}
          {node.type === "video" && (
            <div className="group cursor-pointer" onClick={(e) => { e.stopPropagation(); setShowPreview(true); }}>
              <video
                src={node.output}
                className="mt-1 max-h-32 w-full rounded border object-contain bg-background group-hover:opacity-80 transition-opacity"
                muted
                playsInline
              />
              <span className="text-[9px] text-muted-foreground group-hover:text-primary transition-colors mt-0.5 block">Click to preview</span>
            </div>
          )}
          {node.type === "input" && (
            <div className="italic text-muted-foreground text-[10px] line-clamp-3">
              "{node.output}"
            </div>
          )}
          {node.type === "output" && parsedCampaignOutput && (
            <div className="space-y-1.5">
              <span className="text-[9px] font-semibold text-primary uppercase tracking-wider block">Generated Campaign Assets</span>
              <div className="grid grid-cols-2 gap-1.5">
                {parsedCampaignOutput.image && (
                  <a href={parsedCampaignOutput.image} target="_blank" rel="noreferrer" className="block relative group">
                    <img
                      src={parsedCampaignOutput.image}
                      className="h-14 w-full rounded object-cover border bg-background group-hover:opacity-80 transition-opacity"
                      alt="preview"
                    />
                  </a>
                )}
                {parsedCampaignOutput.video && (
                  <a href={parsedCampaignOutput.video} target="_blank" rel="noreferrer" className="h-14 w-full rounded bg-primary/10 flex flex-col items-center justify-center border border-primary/20 text-[8px] font-bold text-primary hover:bg-primary/20 transition-colors">
                    <span>🎥 WATCH</span>
                    <span>VIDEO</span>
                  </a>
                )}
              </div>
              {parsedCampaignOutput.audio && (
                <div className="text-[8px] font-medium text-muted-foreground flex items-center justify-between bg-background p-1 rounded border">
                  <span>🔊 Voiceover Audio</span>
                  <a href={parsedCampaignOutput.audio} target="_blank" rel="noreferrer" className="text-primary hover:underline">Download</a>
                </div>
              )}
              {parsedCampaignOutput.text && (
                <div className="text-[9px] text-muted-foreground bg-background p-1.5 rounded border line-clamp-3 leading-snug">
                  {parsedCampaignOutput.text}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Prompt used for generation */}
      {node.props?.prompt_used && (
        <div className="border-t border-border bg-muted/10 px-3 py-1.5">
          <span className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider">Prompt</span>
          <p className="mt-0.5 text-[10px] text-muted-foreground line-clamp-3 italic leading-tight">
            "{node.props.prompt_used}"
          </p>
        </div>
      )}

      {/* Resize handle — bottom-right corner */}
      <div
        className="absolute bottom-0 right-0 h-3 w-3 cursor-nwse-resize opacity-0 hover:opacity-100 transition-opacity"
        onMouseDown={(e) => {
          e.stopPropagation();
          onResizeStart(node.id, e);
        }}
      >
        <svg viewBox="0 0 12 12" className="h-3 w-3 text-muted-foreground">
          <path d="M11 1v10H1" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      {/* Fullscreen preview modal */}
      {showPreview && node.output && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={(e) => { e.stopPropagation(); setShowPreview(false); }}
        >
          {/* Close button */}
          <button
            className="absolute top-4 right-4 p-2 rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors"
            onClick={(e) => { e.stopPropagation(); setShowPreview(false); }}
            aria-label="Close preview"
          >
            <X size={24} />
          </button>

          {/* Download button in modal */}
          <button
            className="absolute top-4 right-16 p-2 rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors"
            onClick={(e) => { e.stopPropagation(); handleAssetDownload(node); }}
            aria-label="Download"
          >
            <Download size={20} />
          </button>

          {/* Preview content */}
          <div className="max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            {node.type === "image" && (
              <img
                src={node.output}
                alt="Preview"
                className="max-w-full max-h-[85vh] rounded-lg shadow-2xl object-contain"
              />
            )}
            {node.type === "video" && (
              <video
                src={node.output}
                controls
                autoPlay
                className="max-w-full max-h-[85vh] rounded-lg shadow-2xl"
              />
            )}
            {node.type === "audio" && (
              <div className="bg-card rounded-lg p-8 shadow-2xl flex flex-col items-center gap-4">
                <p className="text-sm font-medium text-foreground">{node.label}</p>
                <audio src={node.output} controls autoPlay className="w-80" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default CanvasNode;
