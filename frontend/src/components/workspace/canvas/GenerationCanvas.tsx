/**
 * GenerationCanvas — the main ComfyUI-style node canvas for generation tasks.
 * Orchestrates NodeLibraryPanel, CanvasViewport, InspectorPanel, CanvasToolbar.
 */

import { useEffect, useCallback, useState } from "react";
import type { PipelineState, NodeType } from "@/components/workspace/canvas/graphModel";
import { addNode } from "@/components/workspace/canvas/graphModel";
import { useCanvasGraph } from "@/components/workspace/canvas/useCanvasGraph";
import { usePipelineRunner } from "@/components/workspace/canvas/usePipelineRunner";
import { NodeLibraryPanel } from "@/components/workspace/canvas/NodeLibraryPanel";
import { CanvasViewport } from "@/components/workspace/canvas/CanvasViewport";
import { InspectorPanel } from "@/components/workspace/canvas/InspectorPanel";
import { CanvasToolbar } from "@/components/workspace/canvas/CanvasToolbar";
import { CanvasContextMenu } from "@/components/workspace/canvas/CanvasContextMenu";

interface GenerationCanvasProps {
  projectId: string;
  taskId: string;
  initialState?: PipelineState;
}

export function GenerationCanvas({ projectId, taskId, initialState }: GenerationCanvasProps) {
  const { state, dispatch } = useCanvasGraph(initialState);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
  } | null>(null);

  const { run, save, isRunning, isSaving } = usePipelineRunner({
    projectId,
    taskId,
    onStateUpdate: (pipeline) => dispatch({ type: "SET_PIPELINE", pipeline }),
  });

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Delete" || e.key === "Backspace") {
        if (state.selectedNodeId) {
          dispatch({ type: "DELETE_NODE", nodeId: state.selectedNodeId });
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [state.selectedNodeId, dispatch]);

  const selectedNode = state.pipeline.nodes.find((n) => n.id === state.selectedNodeId) ?? null;

  const handleContextMenu = useCallback((nodeId: string, e: React.MouseEvent) => {
    setContextMenu({ x: e.clientX, y: e.clientY, nodeId });
  }, []);

  const handleDuplicate = useCallback(
    (nodeId: string) => {
      const node = state.pipeline.nodes.find((n) => n.id === nodeId);
      if (node) {
        dispatch({ type: "ADD_NODE", nodeType: node.type as NodeType, x: node.x + 30, y: node.y + 30 });
      }
    },
    [state.pipeline.nodes, dispatch]
  );

  const handleConnect = useCallback(
    (_nodeId: string) => {
      // Connect-to mode — user clicks another node to connect
      // For simplicity, we just select the source node for now
    },
    []
  );

  const handleDelete = useCallback(
    (nodeId: string) => {
      dispatch({ type: "DELETE_NODE", nodeId });
    },
    [dispatch]
  );

  return (
    <div className="flex h-full flex-col">
      <CanvasToolbar
        onRun={() => run(state.pipeline)}
        onSave={() => save(state.pipeline)}
        isRunning={isRunning}
        isSaving={isSaving}
      />
      <div className="flex flex-1 overflow-hidden">
        <NodeLibraryPanel />
        <CanvasViewport
          pipeline={state.pipeline}
          selectedNodeId={state.selectedNodeId}
          dispatch={dispatch}
          onContextMenu={handleContextMenu}
        />
        <InspectorPanel node={selectedNode} />
      </div>

      {/* Context menu */}
      {contextMenu && (
        <CanvasContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          nodeId={contextMenu.nodeId}
          onDuplicate={handleDuplicate}
          onConnect={handleConnect}
          onDelete={handleDelete}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}

export default GenerationCanvas;
