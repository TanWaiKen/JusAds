import { useEffect, useCallback, useState } from "react";
import type { PipelineState, NodeType } from "@/components/workspace/canvas/graphModel";
import { useCanvasGraph } from "@/components/workspace/canvas/useCanvasGraph";
import { usePipelineRunner } from "@/components/workspace/canvas/usePipelineRunner";
import { NodeLibraryPanel } from "@/components/workspace/canvas/NodeLibraryPanel";
import { CanvasViewport } from "@/components/workspace/canvas/CanvasViewport";
import { InspectorPanel } from "@/components/workspace/canvas/InspectorPanel";
import { CanvasToolbar } from "@/components/workspace/canvas/CanvasToolbar";
import { CanvasContextMenu } from "@/components/workspace/canvas/CanvasContextMenu";
import { ChatbotPanel } from "@/components/workspace/canvas/ChatbotPanel";

interface GenerationCanvasProps {
  projectId: string;
  taskId: string;
  initialState?: PipelineState;
}

export function GenerationCanvas({ projectId, taskId, initialState }: GenerationCanvasProps) {
  const { state, dispatch } = useCanvasGraph(initialState);
  const [activeTab, setActiveTab] = useState<"chatbot" | "inspector">("chatbot");
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
        
        {/* Tabbed Right Panel */}
        <div className="w-80 shrink-0 border-l bg-background flex flex-col h-full">
          <div className="flex border-b border-border text-xs font-semibold select-none bg-muted/20">
            <button
              onClick={() => setActiveTab("chatbot")}
              className={`flex-1 py-3 text-center border-b-2 transition-all cursor-pointer ${
                activeTab === "chatbot"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Agent Chatbot
            </button>
            <button
              onClick={() => setActiveTab("inspector")}
              className={`flex-1 py-3 text-center border-b-2 transition-all cursor-pointer ${
                activeTab === "inspector"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Inspector
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {activeTab === "chatbot" ? (
              <ChatbotPanel
                projectId={projectId}
                taskId={taskId}
                onStateUpdate={(pipeline) => dispatch({ type: "SET_PIPELINE", pipeline })}
              />
            ) : (
              <InspectorPanel node={selectedNode} />
            )}
          </div>
        </div>
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
