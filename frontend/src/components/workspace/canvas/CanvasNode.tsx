/**
 * CanvasNode — a single node on the Generation Canvas.
 * Displays type color, label, input/output ports, status indicator, and selection ring.
 */

import type { CanvasNode as CanvasNodeType, NodeStatus } from "@/components/workspace/canvas/graphModel";

interface CanvasNodeProps {
  node: CanvasNodeType;
  isSelected: boolean;
  onSelect: (nodeId: string) => void;
  onDragStart: (nodeId: string, e: React.MouseEvent) => void;
  onPortDragStart: (nodeId: string, portType: "output") => void;
  onPortDrop: (nodeId: string, portType: "input") => void;
  onContextMenu: (nodeId: string, e: React.MouseEvent) => void;
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
  onDragStart,
  onPortDragStart,
  onPortDrop,
  onContextMenu,
}: CanvasNodeProps) {
  const colorClass = NODE_COLORS[node.type] ?? "bg-gray-500";
  const statusClass = STATUS_INDICATORS[node.status];

  // Parse output JSON for output node summaries
  let parsedCampaignOutput: Record<string, string> | null = null;
  if (node.type === "output" && node.output) {
    try {
      parsedCampaignOutput = JSON.parse(node.output);
    } catch {
      // not json
    }
  }

  // Double width if node has visual output to show
  const nodeWidth = node.output && (node.type === "image" || node.type === "video" || node.type === "output" || node.type === "text") ? 220 : 180;

  return (
    <div
      className={`absolute select-none rounded-lg border bg-card shadow-md transition-all ${
        isSelected ? "ring-2 ring-primary shadow-lg z-10" : "hover:shadow-lg"
      }`}
      style={{ left: node.x, top: node.y, width: nodeWidth }}
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
        <div className={`ml-auto h-2.5 w-2.5 rounded-full ${statusClass}`} />
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
            <img
              src={node.output}
              alt="Generated Ad"
              className="mt-1 max-h-32 w-full rounded border object-contain bg-background shadow-inner"
            />
          )}
          {node.type === "audio" && (
            <audio
              src={node.output}
              controls
              className="mt-1 w-full scale-90 origin-left"
            />
          )}
          {node.type === "video" && (
            <video
              src={node.output}
              controls
              className="mt-1 max-h-32 w-full rounded border object-contain bg-background"
            />
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
    </div>
  );
}

export default CanvasNode;
