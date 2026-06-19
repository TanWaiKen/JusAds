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

  return (
    <div
      className={`absolute select-none rounded-lg border bg-card shadow-md transition-shadow ${
        isSelected ? "ring-2 ring-primary shadow-lg" : "hover:shadow-lg"
      }`}
      style={{ left: node.x, top: node.y, width: 180 }}
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
      <div className="relative flex items-center justify-between px-1 py-3">
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

        <span className="text-xs text-muted-foreground">{node.type}</span>

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
    </div>
  );
}

export default CanvasNode;
