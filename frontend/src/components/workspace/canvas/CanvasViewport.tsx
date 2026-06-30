/**
 * CanvasViewport — pannable/zoomable area for the Generation Canvas.
 * Renders SVG edge layer and positioned CanvasNode components.
 */

import { useRef, useState, useCallback } from "react";
import type { CanvasAction } from "@/components/workspace/canvas/useCanvasGraph";
import type { PipelineState, CanvasEdge } from "@/components/workspace/canvas/graphModel";
import { screenToCanvas } from "@/components/workspace/canvas/graphModel";
import { CanvasNode } from "@/components/workspace/canvas/CanvasNode";

interface CanvasViewportProps {
  pipeline: PipelineState;
  selectedNodeId: string | null;
  dispatch: React.Dispatch<CanvasAction>;
  onContextMenu: (nodeId: string, e: React.MouseEvent) => void;
}

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 2.0;
const NODE_WIDTH = 180;
const NODE_HEIGHT = 80;

export function CanvasViewport({
  pipeline,
  selectedNodeId,
  dispatch,
  onContextMenu,
}: CanvasViewportProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [dragNodeId, setDragNodeId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null);
  const [tempEdgeEnd, setTempEdgeEnd] = useState<{ x: number; y: number } | null>(null);

  const { viewport, nodes, edges } = pipeline;

  // Pan handling
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget || (e.target as HTMLElement).tagName === "svg") {
        setIsPanning(true);
        setPanStart({ x: e.clientX - viewport.panX, y: e.clientY - viewport.panY });
        dispatch({ type: "SELECT_NODE", nodeId: null });
      }
    },
    [viewport.panX, viewport.panY, dispatch]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning) {
        dispatch({
          type: "PAN",
          panX: e.clientX - panStart.x,
          panY: e.clientY - panStart.y,
        });
      } else if (dragNodeId) {
        const canvasPoint = screenToCanvas(
          { x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y },
          viewport
        );
        dispatch({ type: "MOVE_NODE", nodeId: dragNodeId, x: canvasPoint.x, y: canvasPoint.y });
      } else if (connectingFrom && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const canvasPoint = screenToCanvas(
          { x: e.clientX - rect.left, y: e.clientY - rect.top },
          viewport
        );
        setTempEdgeEnd(canvasPoint);
      }
    },
    [isPanning, panStart, dragNodeId, dragOffset, connectingFrom, viewport, dispatch]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    setDragNodeId(null);
    if (connectingFrom) {
      dispatch({ type: "CANCEL_CONNECTION" });
      setConnectingFrom(null);
      setTempEdgeEnd(null);
    }
  }, [connectingFrom, dispatch]);

  // Zoom handling
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
      const newZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, viewport.zoom * zoomFactor));

      const newPanX = mouseX - (mouseX - viewport.panX) * (newZoom / viewport.zoom);
      const newPanY = mouseY - (mouseY - viewport.panY) * (newZoom / viewport.zoom);

      dispatch({ type: "ZOOM", zoom: newZoom, panX: newPanX, panY: newPanY });
    },
    [viewport, dispatch]
  );

  // Node drag
  const handleNodeDragStart = useCallback(
    (nodeId: string, e: React.MouseEvent) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const screenNodeX = node.x * viewport.zoom + viewport.panX + rect.left;
      const screenNodeY = node.y * viewport.zoom + viewport.panY + rect.top;

      setDragNodeId(nodeId);
      setDragOffset({
        x: e.clientX - screenNodeX,
        y: e.clientY - screenNodeY,
      });
    },
    [nodes, viewport]
  );

  // Connection handling
  const handlePortDragStart = useCallback((nodeId: string) => {
    setConnectingFrom(nodeId);
  }, []);

  const handlePortDrop = useCallback(
    (nodeId: string) => {
      if (connectingFrom && connectingFrom !== nodeId) {
        dispatch({ type: "ADD_EDGE", from: connectingFrom, to: nodeId });
      }
      setConnectingFrom(null);
      setTempEdgeEnd(null);
    },
    [connectingFrom, dispatch]
  );

  // Edge path calculation
  const getEdgePath = useCallback(
    (edge: CanvasEdge): string => {
      const fromNode = nodes.find((n) => n.id === edge.from);
      const toNode = nodes.find((n) => n.id === edge.to);
      if (!fromNode || !toNode) return "";

      const x1 = fromNode.x + NODE_WIDTH;
      const y1 = fromNode.y + NODE_HEIGHT / 2;
      const x2 = toNode.x;
      const y2 = toNode.y + NODE_HEIGHT / 2;

      const dx = Math.abs(x2 - x1) * 0.5;
      return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    },
    [nodes]
  );

  // Temp edge for connection in progress
  const getTempEdgePath = useCallback((): string => {
    if (!connectingFrom || !tempEdgeEnd) return "";
    const fromNode = nodes.find((n) => n.id === connectingFrom);
    if (!fromNode) return "";

    const x1 = fromNode.x + NODE_WIDTH;
    const y1 = fromNode.y + NODE_HEIGHT / 2;
    const x2 = tempEdgeEnd.x;
    const y2 = tempEdgeEnd.y;

    const dx = Math.abs(x2 - x1) * 0.5;
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
  }, [connectingFrom, tempEdgeEnd, nodes]);

  // Drop handling for nodes from library
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const nodeType = e.dataTransfer.getData("application/canvas-node-type");
      if (!nodeType) return;

      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const canvasPoint = screenToCanvas(
        { x: e.clientX - rect.left, y: e.clientY - rect.top },
        viewport
      );

      dispatch({
        type: "ADD_NODE",
        nodeType: nodeType as Parameters<typeof dispatch>[0] extends { nodeType: infer T } ? T : never,
        x: canvasPoint.x,
        y: canvasPoint.y,
      });
    },
    [viewport, dispatch]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 overflow-hidden bg-muted/30 cursor-grab active:cursor-grabbing"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      {/* Transform group */}
      <div
        className="absolute inset-0 origin-top-left"
        style={{
          transform: `translate(${viewport.panX}px, ${viewport.panY}px) scale(${viewport.zoom})`,
        }}
      >
        {/* SVG edge layer */}
        <svg className="absolute inset-0 h-full w-full pointer-events-none" style={{ width: "10000px", height: "10000px" }}>
          {edges.map((edge) => (
            <path
              key={edge.id}
              d={getEdgePath(edge)}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              className="text-muted-foreground/60"
            />
          ))}
          {connectingFrom && tempEdgeEnd && (
            <path
              d={getTempEdgePath()}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeDasharray="6 3"
              className="text-primary/60"
            />
          )}
        </svg>

        {/* Nodes */}
        {nodes.map((node) => (
          <CanvasNode
            key={node.id}
            node={node}
            isSelected={selectedNodeId === node.id}
            onSelect={(id) => dispatch({ type: "SELECT_NODE", nodeId: id })}
            onDragStart={handleNodeDragStart}
            onPortDragStart={handlePortDragStart}
            onPortDrop={handlePortDrop}
            onContextMenu={onContextMenu}
          />
        ))}
      </div>

      {/* Zoom indicator */}
      <div className="absolute bottom-3 right-3 rounded bg-background/80 px-2 py-1 text-xs text-muted-foreground backdrop-blur-sm">
        {Math.round(viewport.zoom * 100)}%
      </div>
    </div>
  );
}

export default CanvasViewport;
