import { useEffect, useCallback, useState, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { toast } from "sonner";
import type { PipelineState, NodeType } from "@/components/workspace/canvas/graphModel";
import { useCanvasGraph } from "@/components/workspace/canvas/useCanvasGraph";
import { usePipelineRunner } from "@/components/workspace/canvas/usePipelineRunner";
import { getTask, savePipeline } from "@/services/projectService";
import { CanvasViewport } from "@/components/workspace/canvas/CanvasViewport";
import { InspectorPanel } from "@/components/workspace/canvas/InspectorPanel";
import { CanvasToolbar } from "@/components/workspace/canvas/CanvasToolbar";
import { CanvasContextMenu } from "@/components/workspace/canvas/CanvasContextMenu";
import { ChatbotPanel, mapGeneratedAds } from "@/components/workspace/canvas/ChatbotPanel";
import { OutputGallery } from "@/components/workspace/canvas/OutputGallery";
import { VideoPlanStoryboard } from "@/components/workspace/canvas/VideoPlanStoryboard";
import { SettingsPanel } from "@/components/workspace/canvas/SettingsPanel";
import type { GenerationSettings } from "@/components/workspace/canvas/SettingsPanel";
import { HookSearchPanel } from "@/components/workspace/canvas/HookSearchPanel";
import type { GeneratedAdView, VideoPlan } from "@/services/generationService";
import { executeVideoPlan, getGeneratedAds, normalizeVideoPlan } from "@/services/generationService";

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
  const [revisionContext, setRevisionContext] = useState<{ parentAdId?: string; parentAssetUrl?: string } | null>(null);

  // Auto-switch to Inspector tab when a non-reference node is selected.
  // Reference nodes are selected transiently during upload — don't steal focus
  // from the chatbot tab so the user can keep adding references without interruption.
  useEffect(() => {
    if (!state.selectedNodeId) return;
    const node = state.pipeline.nodes.find((n) => n.id === state.selectedNodeId);
    if (node?.type === "reference") return;
    let active = true;
    queueMicrotask(() => {
      if (active) setActiveTab("inspector");
    });
    return () => {
      active = false;
    };
  }, [state.selectedNodeId, state.pipeline.nodes]);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    nodeId: string;
  } | null>(null);

  // Lifted output state so both chat and the Outputs tab share it.
  const [outputs, setOutputs] = useState<GeneratedAdView[]>([]);
  const [videoPlan, setVideoPlan] = useState<VideoPlan | null>(null);
  const [planRendering, setPlanRendering] = useState(false);

  // References are managed locally inside ChatbotPanel (same as Easy Mode).
  // After generation the backend emits an "input" node whose reference_urls
  // prop can be edited from the InspectorPanel — no canvas reference nodes needed.

  // Settings state (unified, drives the SettingsPanel). Video generation always uses V3 Grid.
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hookSearchOpen, setHookSearchOpen] = useState(false);

  // The canvas and the Outputs tab must read the same persisted pipeline.
  // Guided generation can update a node before the chat panel emits its local
  // output callback; deriving the gallery here prevents stale counts/previews.
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) setOutputs(mapGeneratedAds(state.pipeline));
    });
    return () => {
      active = false;
    };
  }, [state.pipeline]);

  // A render can finish while a previous server version still has a pending
  // video_plan persisted. Prefer the already-saved final MP4 over that stale
  // approval gate so reopening Outputs shows the completed video immediately.
  useEffect(() => {
    let cancelled = false;

    void getGeneratedAds(projectId, taskId).then((persistedAds) => {
      if (cancelled || persistedAds.length === 0) return;
      setOutputs(persistedAds);
      const hasFinalV3Video = persistedAds.some(
        (ad) => ad.mediaType === "video" && /\/final_video\.mp4(?:\?|$)/.test(ad.publicUrl ?? "")
      );
      // Hide the storyboard approval UI if a final video already exists.
      // The plan data itself stays in state.pipeline.video_plan for re-renders.
      if (hasFinalV3Video) setVideoPlan(null);
    });

    return () => { cancelled = true; };
  }, [projectId, taskId]);

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
    complianceEnabled: loadedSettings.complianceEnabled === true,
    creativeStyle: (loadedSettings.creativeStyle as GenerationSettings["creativeStyle"]) ?? "meme_shock",
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

  // Render an approved V3 storyboard and wait for its explicit terminal state.
  const handleContinuePlan = useCallback(async (approvedPlan: VideoPlan) => {
    setPlanRendering(true);
    let completedPipeline: PipelineState | null = null;
    let renderError: string | null = null;

    try {
      for await (const event of executeVideoPlan(
        projectId, taskId, approvedPlan, !settings.complianceEnabled
      )) {
        if (event.pipeline_state) {
          completedPipeline = event.pipeline_state;
          dispatch({ type: "SET_PIPELINE", pipeline: event.pipeline_state });
          setOutputs(mapGeneratedAds(event.pipeline_state));
        }

        if (event.error) {
          renderError = event.error;
        } else if (event.status === "failed") {
          const details = event.data;
          renderError = typeof details === "object" && details !== null && typeof (details as { error?: unknown }).error === "string"
            ? (details as { error: string }).error
            : "Video render failed.";
        }
      }

      const [persistedAds, persistedTask] = await Promise.all([
        getGeneratedAds(projectId, taskId),
        getTask(projectId, taskId),
      ]);
      const persistedPipeline = persistedTask.type === "generation"
        ? persistedTask.pipeline_state
        : null;
      const hasFinalVideo = persistedAds.some(
        (ad) => ad.mediaType === "video" && /\/final_video\.mp4(?:\?|$)/.test(ad.publicUrl ?? "")
      );

      if (persistedPipeline) {
        dispatch({ type: "SET_PIPELINE", pipeline: persistedPipeline });
      }

      if (renderError) {
        toast.error(`Video render error: ${renderError}`);
      } else if (hasFinalVideo) {
        // Hide storyboard approval UI but keep video_plan in pipeline_state
        // so the re-render button on the video node can reuse it.
        setVideoPlan(null);
        setActiveTab("outputs");
        setOutputs(persistedAds);
        toast.success("Video rendered successfully!");
      } else if (completedPipeline) {
        toast.error("Video render completed without a persisted final video.");
      } else {
        toast.error("Video render ended before the final video was confirmed.");
      }
    } catch (err) {
      console.error(err);
      toast.error("Failed to render the video");
    } finally {
      setPlanRendering(false);
    }
  }, [projectId, taskId, settings.complianceEnabled, dispatch]);

  // Re-render video only — reuses the existing plan from pipeline_state.
  const [isRerendering, setIsRerendering] = useState(false);
  const handleRerender = useCallback(async () => {
    // Persisted backend plans use snake_case; normalize before serializing again.
    const rawPlan = (state.pipeline as unknown as Record<string, unknown>).video_plan;
    const savedPlan = normalizeVideoPlan(rawPlan);
    if (!savedPlan) {
      toast.error("No saved storyboard found — generate a video first before re-rendering.");
      return;
    }
    const usableFrameCount = (savedPlan.frameUrls ?? [])
      .filter((url) => url.trim()).length;
    const hasAllStoryboardAssets = Boolean(savedPlan.sceneGridUrl)
      && usableFrameCount >= savedPlan.scenes.length;
    if (savedPlan.pipelineVersion !== "v3_grid" || !hasAllStoryboardAssets) {
      toast.error("This storyboard is legacy or incomplete. Regenerate a V3 storyboard before rendering.");
      return;
    }
    setIsRerendering(true);
    try {
      let completedPipeline: PipelineState | null = null;
      for await (const event of executeVideoPlan(
        projectId, taskId, savedPlan, !settings.complianceEnabled
      )) {
        if (event.pipeline_state) {
          completedPipeline = event.pipeline_state;
          dispatch({ type: "SET_PIPELINE", pipeline: event.pipeline_state });
          setOutputs(mapGeneratedAds(event.pipeline_state));
        }
        if (event.error) {
          toast.error(`Re-render error: ${event.error}`);
        }
      }
      if (completedPipeline) {
        const persistedAds = await getGeneratedAds(projectId, taskId);
        setOutputs(persistedAds);
        setActiveTab("outputs");
        toast.success("Video re-rendered successfully!");
      }
    } catch (err) {
      console.error(err);
      toast.error("Failed to re-render the video");
    } finally {
      setIsRerendering(false);
    }
  }, [projectId, taskId, settings.complianceEnabled, state.pipeline, dispatch]);

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

      if (e.key === "Delete") {
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

  const handleVideoPlanUpdate = useCallback((plan: VideoPlan | null, revealOutputs = true): void => {
    setVideoPlan(plan);
    if (plan && revealOutputs) {
      // A new storyboard needs enough horizontal room to review its keyframes and scene details.
      setActiveTab("outputs");
      setIsPanelMaximized(true);
    }
  }, []);

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
    () => {
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
        taskId={taskId}
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
            onOpenHookSearch={() => setHookSearchOpen(true)}
            onClose={() => setSettingsOpen(false)}
          />
        )}

        {/* Hook Search Panel */}
        {hookSearchOpen && (
          <HookSearchPanel
            creativeStyle={settings.creativeStyle}
            market={settings.market}
            ethnicity={settings.targetEthnicity}
            productCategory={settings.productCategory}
            onSelectHook={(video) => {
              setHookSearchOpen(false);
              // Use the hook video URL as a chat prompt for the Director
              setChatbotPrompt(
                `Use this YouTube Short as a hook reference for the ad opening: ${video.url} — "${video.title}". ` +
                `Replicate the energy, transition style, and pacing of this clip in the first 2–3 seconds.`
              );
              setActiveTab("chatbot");
            }}
            onClose={() => setHookSearchOpen(false)}
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
              Ad helper
            </button>
            <button
              onClick={() => setActiveTab("outputs")}
              className={`flex-1 py-3 text-center border-b-2 transition-all cursor-pointer ${
                activeTab === "outputs"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              My results{outputs.length > 0 ? ` (${outputs.length})` : ""}
            </button>
            <button
              onClick={() => setActiveTab("inspector")}
              className={`flex-1 py-3 text-center border-b-2 transition-all cursor-pointer ${
                activeTab === "inspector"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Details
            </button>
            <button
              onClick={() => setIsPanelMaximized((prev) => !prev)}
              className="px-3 py-3 text-muted-foreground hover:text-foreground transition-colors cursor-pointer border-b-2 border-transparent"
              title={isPanelMaximized ? "Restore panel" : "Expand panel"}
              aria-label={isPanelMaximized ? "Restore panel size" : "Expand panel"}
            >
              {isPanelMaximized ? "⇥" : "⇤"}
            </button>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeTab === "chatbot" ? (
              <ChatbotPanel
                projectId={projectId}
                taskId={taskId}
                onStateUpdate={(pipeline) => dispatch({ type: "SET_PIPELINE", pipeline })}
                targetPlatform={settings.targetPlatform}
                complianceEnabled={settings.complianceEnabled}
                targetEthnicity={settings.targetEthnicity}
                triggerPrompt={chatbotPrompt}
                onTriggerPromptUsed={() => setChatbotPrompt(null)}
                revisionContext={revisionContext}
                onRevisionContextUsed={() => setRevisionContext(null)}
                generationOptions={{
                  ageGroup: settings.ageGroup,
                  market: settings.market,
                  language: settings.language,
                  productName: settings.productName,
                  productCategory: settings.productCategory,
                  gender: settings.gender,
                  creativeStyle: settings.creativeStyle,
                }}
                initialPipelineState={state.pipeline}
                onOutputsUpdate={setOutputs}
                onVideoPlanUpdate={handleVideoPlanUpdate}
              />
            ) : activeTab === "outputs" ? (
              <div className="h-full overflow-y-auto">
                {videoPlan && (
                  <div className="border-b p-3">
                    <VideoPlanStoryboard
                      key={videoPlan.planId}
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
                projectId={projectId}
                taskId={taskId}
                onUpdateProps={(nodeId, updates) => dispatch({ type: "UPDATE_NODE_PROPS", nodeId, ...updates })}
                onDelete={handleDelete}
                onSendRevision={(node, comment) => {
                  const isAssetNode = node.type === "image" || node.type === "video" || node.type === "audio";
                  setRevisionContext({
                    parentAdId: isAssetNode ? (node.props.ad_id || undefined) : undefined,
                    parentAssetUrl: isAssetNode ? (node.props.asset_url || node.output || undefined) : undefined,
                  });
                  // Build a prompt that includes explicit generation action words so
                  // the backend intent detector fires the pipeline, not just a chat reply.
                  const mediaAction: Record<string, string> = {
                    orchestrator: "Regenerate the full video ad (director plan, character sheet, and scene grid)",
                    image: "Regenerate the image",
                    video: "Regenerate the video",
                    audio: "Regenerate the audio",
                    text: "Regenerate the ad copy",
                  };
                  const action = mediaAction[node.type] ?? `Regenerate the ${node.type}`;
                  setChatbotPrompt(`${action} with this feedback: ${comment}`);
                  setActiveTab("chatbot");
                }}
                onRerender={() => handleRerender()}
                isRerendering={isRerendering}
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
