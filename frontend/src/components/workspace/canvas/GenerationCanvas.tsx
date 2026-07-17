import { useEffect, useCallback, useState, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { toast } from "sonner";
import type { PipelineState, NodeType } from "@/components/workspace/canvas/graphModel";
import { useCanvasGraph } from "@/components/workspace/canvas/useCanvasGraph";
import { usePipelineRunner } from "@/components/workspace/canvas/usePipelineRunner";
import { savePipeline } from "@/services/taskApi";
import { CanvasViewport } from "@/components/workspace/canvas/CanvasViewport";
import { InspectorPanel } from "@/components/workspace/canvas/InspectorPanel";
import { CanvasToolbar } from "@/components/workspace/canvas/CanvasToolbar";
import { CanvasContextMenu } from "@/components/workspace/canvas/CanvasContextMenu";
import { ChatbotPanel } from "@/components/workspace/canvas/ChatbotPanel";
import { OutputGallery } from "@/components/workspace/canvas/OutputGallery";
import { VideoPlanStoryboard } from "@/components/workspace/canvas/VideoPlanStoryboard";
import { SettingsPanel } from "@/components/workspace/canvas/SettingsPanel";
import type { GenerationSettings } from "@/components/workspace/canvas/SettingsPanel";
import type { GeneratedAdView, VideoPlan } from "@/services/generationApi";
import { executeVideoPlan } from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

interface GenerationCanvasProps {
  projectId: string;
  taskId: string;
  initialState?: PipelineState;
}

export function GenerationCanvas({ projectId, taskId, initialState }: GenerationCanvasProps) {
  const { state, dispatch } = useCanvasGraph(initialState);
  const [activeTab, setActiveTab] = useState<"chatbot" | "outputs" | "inspector">("chatbot");
  const [chatbotPrompt, setChatbotPrompt] = useState<string | null>(null);

  // Auto-switch to Inspector tab when a node is selected
  useEffect(() => {
    if (state.selectedNodeId) {
      setActiveTab("inspector");
    }
  }, [state.selectedNodeId]);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
  } | null>(null);

  // Lifted output state so both chat and the Outputs tab share it.
  const [outputs, setOutputs] = useState<GeneratedAdView[]>([]);
  const [videoPlan, setVideoPlan] = useState<VideoPlan | null>(null);
  const [planRendering, setPlanRendering] = useState(false);

  // Settings state (unified, drives the SettingsPanel)
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Load persisted settings from initialState if available (B4).
  const loadedSettings = (() => {
    if (!initialState) return {};
    const raw = (initialState as unknown as Record<string, unknown>).generation_settings;
    if (typeof raw === "object" && raw !== null && !Array.isArray(raw)) return raw as Record<string, unknown>;
    return {};
  })();

  const [settings, setSettings] = useState<GenerationSettings>({
    targetPlatform: (loadedSettings.targetPlatform as GenerationSettings["targetPlatform"]) ?? "tiktok",
    targetEthnicity: (loadedSettings.targetEthnicity as GenerationSettings["targetEthnicity"]) ?? "all",
    ageGroup: (loadedSettings.ageGroup as GenerationSettings["ageGroup"]) ?? "all_ages",
    gender: (loadedSettings.gender as GenerationSettings["gender"]) ?? "female",
    market: (loadedSettings.market as GenerationSettings["market"]) ?? "malaysia",
    language: (loadedSettings.language as GenerationSettings["language"]) ?? "auto",
    productName: (typeof loadedSettings.productName === "string" ? loadedSettings.productName : "") as string,
    productCategory: (typeof loadedSettings.productCategory === "string" ? loadedSettings.productCategory : "") as string,
    complianceEnabled: loadedSettings.complianceEnabled !== false,
    videoV2Enabled: loadedSettings.videoV2Enabled === true,
  });

  // Debounced auto-save of settings to pipeline_state.generation_settings (B4).
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateSettings = (patch: Partial<GenerationSettings>): void => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      // Debounce save (500ms after last change).
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        const pipelineWithSettings = {
          ...state.pipeline,
          generation_settings: next,
        } as unknown as typeof state.pipeline;
        savePipeline(projectId, taskId, pipelineWithSettings, "saved").catch(() => {});
      }, 500);
      return next;
    });
  };

  // Video V2: handle the Continue button from the Outputs tab storyboard.
  const handleContinuePlan = useCallback(async (approvedPlan: VideoPlan) => {
    setPlanRendering(true);
    try {
      for await (const event of executeVideoPlan(
        projectId, taskId, approvedPlan, !settings.complianceEnabled
      )) {
        if (event.pipeline_state) {
          dispatch({ type: "SET_PIPELINE", pipeline: event.pipeline_state });
        }
        if (event.error) {
          toast.error(`Video render error: ${event.error}`);
        }
      }
      setVideoPlan(null);
      toast.success("Video rendered successfully!");
    } catch (err) {
      console.error(err);
      toast.error("Failed to render the video");
    } finally {
      setPlanRendering(false);
    }
  }, [projectId, taskId, settings.complianceEnabled, dispatch]);

  const { save, isSaving } = usePipelineRunner({
    projectId,
    taskId,
    onStateUpdate: (pipeline) => dispatch({ type: "SET_PIPELINE", pipeline }),
  });

  // Ctrl+S keyboard shortcut for saving
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        save(state.pipeline);
      }

      if (e.key === "Delete" || e.key === "Backspace") {
        if (state.selectedNodeId) {
          dispatch({ type: "DELETE_NODE", nodeId: state.selectedNodeId });
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [state.selectedNodeId, state.pipeline, dispatch, save]);

  const selectedNode = state.pipeline.nodes.find((n) => n.id === state.selectedNodeId) ?? null;

  const handleContextMenu = useCallback((nodeId: string, e: React.MouseEvent) => {
    setContextMenu({ x: e.clientX, y: e.clientY, nodeId });
  }, []);

  const [panelWidth, setPanelWidth] = useState(380);
  const [isResizing, setIsResizing] = useState(false);
  const [isPanelMaximized, setIsPanelMaximized] = useState(false);

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= 240 && newWidth <= 600) {
        setPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

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
      // Connect-to mode placeholder
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
        projectId={projectId}
        isSaving={isSaving}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="relative flex flex-1 overflow-hidden">
        <CanvasViewport
          pipeline={state.pipeline}
          selectedNodeId={state.selectedNodeId}
          dispatch={dispatch}
          onContextMenu={handleContextMenu}
        />

        {/* Settings Panel (two-tab overlay) */}
        {settingsOpen && (
          <SettingsPanel
            settings={settings}
            onUpdate={updateSettings}
            onClose={() => setSettingsOpen(false)}
          />
        )}

        {/* Tabbed Right Panel */}
        <div
          style={{ width: isPanelMaximized ? "60%" : `${panelWidth}px` }}
          className={`relative shrink-0 border-l bg-background flex flex-col h-full transition-[width] duration-200 ${isResizing ? "select-none" : ""}`}
        >
          {/* Resizer Handle */}
          <div
            onMouseDown={startResizing}
            className={`absolute top-0 bottom-0 left-0 w-1 cursor-col-resize hover:bg-primary/50 transition-colors z-50 ${
              isResizing ? "bg-primary" : "bg-transparent"
            }`}
          />
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
              onClick={() => setActiveTab("outputs")}
              className={`flex-1 py-3 text-center border-b-2 transition-all cursor-pointer ${
                activeTab === "outputs"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Outputs{outputs.length > 0 ? ` (${outputs.length})` : ""}
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
            <button
              onClick={() => setIsPanelMaximized((prev) => !prev)}
              className="px-3 py-3 text-muted-foreground hover:text-foreground transition-colors cursor-pointer border-b-2 border-transparent"
              title={isPanelMaximized ? "Restore panel" : "Expand panel"}
            >
              {isPanelMaximized ? "⇥" : "⇤"}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {activeTab === "chatbot" ? (
              <ChatbotPanel
                projectId={projectId}
                taskId={taskId}
                onStateUpdate={(pipeline) => dispatch({ type: "SET_PIPELINE", pipeline })}
                targetPlatform={settings.targetPlatform}
                complianceEnabled={settings.complianceEnabled}
                videoV3Enabled={settings.videoV2Enabled}
                targetEthnicity={settings.targetEthnicity}
                triggerPrompt={chatbotPrompt}
                onTriggerPromptUsed={() => setChatbotPrompt(null)}
                generationOptions={{
                  ageGroup: settings.ageGroup,
                  market: settings.market,
                  language: settings.language,
                  productName: settings.productName,
                  productCategory: settings.productCategory,
                  gender: settings.gender,
                }}
                initialPipelineState={initialState}
                onOutputsUpdate={setOutputs}
                onVideoPlanUpdate={setVideoPlan}
              />
            ) : activeTab === "outputs" ? (
              <div className="flex flex-col h-full overflow-y-auto">
                {videoPlan && (
                  <div className="border-b p-3">
                    <VideoPlanStoryboard
                      plan={videoPlan}
                      onContinue={handleContinuePlan}
                      isRendering={planRendering}
                    />
                  </div>
                )}
                {outputs.length > 0 ? (
                  <OutputGallery
                    ads={outputs}
                    isSidebar={true}
                    projectId={projectId}
                    taskId={taskId}
                  />
                ) : !videoPlan ? (
                  <div className="flex flex-col items-center justify-center h-full p-8 text-center text-muted-foreground my-auto">
                    <div className="rounded-full bg-muted p-4 mb-4">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                        className="w-8 h-8 text-muted-foreground/60"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M2.25 13.5h3.86a2.25 2.25 0 0 1 2.008 1.24l.885 1.77a2.25 2.25 0 0 0 2.007 1.24h1.98a2.25 2.25 0 0 0 2.007-1.24l.885-1.77a2.25 2.25 0 0 1 2.007-1.24h3.86m-18 0h18"
                        />
                      </svg>
                    </div>
                    <h3 className="font-semibold text-lg text-foreground">No outputs generated yet</h3>
                    <p className="text-sm max-w-sm mt-1">
                      Start a conversation with the Agent Chatbot to generate ad copy, images, audio, or video creatives.
                    </p>
                  </div>
                ) : null}
              </div>
            ) : (
              <InspectorPanel
                node={selectedNode}
                onUpdateProps={(nodeId, updates) => dispatch({ type: "UPDATE_NODE_PROPS", nodeId, ...updates })}
                onDelete={handleDelete}
                onSendRevision={(nodeLabel, comment) => {
                  setChatbotPrompt(`Please revise node "${nodeLabel}" with feedback: ${comment}`);
                  setActiveTab("chatbot");
                }}
              />
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
