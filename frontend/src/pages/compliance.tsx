import { useReducer, useRef, useCallback, useEffect, useState } from "react";
import { useParams, useLocation, useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useComplianceCheck } from "@/hooks/useComplianceCheck";
import { useComplianceRemix } from "@/hooks/useComplianceRemix";
import { useAuth } from "@/hooks/useAuth";
import { projectReducer, initialProjectStore } from "@/reducers/projectReducer";
import { ProjectSidebar } from "@/components/compliance/ProjectSidebar";
import { StepNavigator } from "@/components/compliance/StepNavigator";
import { UploadStep } from "@/components/compliance/UploadStep";
import { CheckStep } from "@/components/compliance/CheckStep";
import { ReviewStep } from "@/components/compliance/ReviewStep";
import { RemixStep } from "@/components/compliance/RemixStep";
import { ComparisonView } from "@/components/compliance/ComparisonView";
import type { UploadParams, Project } from "@/types/compliance";
import { WORKFLOW_STEPS } from "@/types/compliance";
import type { ComplianceResult } from "@/services/complianceApi";
import { API_BASE } from "@/services/complianceApi";
import { savePipeline } from "@/services/taskApi";

gsap.registerPlugin(useGSAP);

/**
 * Derives media type from UploadParams (file MIME type or defaults to "text").
 */
function deriveMediaType(params: UploadParams): Project["mediaType"] {
  if (!params.file) return "text";
  if (params.file.type.startsWith("video/")) return "video";
  if (params.file.type.startsWith("image/")) return "image";
  if (params.file.type.startsWith("audio/")) return "audio";
  return "text";
}

/**
 * Generates a unique project ID.
 */
function generateId(): string {
  return crypto.randomUUID?.() ?? `proj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * ComplianceWorkspace — the top-level orchestrator for the project-based
 * compliance workflow. Replaces the old queue-based layout with a step-driven
 * flow: Upload → Check → Review → Remix → Compare.
 *
 * Requirements: 1.1, 1.2, 1.3, 2.5, 2.6, 3.2, 4.5, 6.3, 8.1, 9.2, 9.4,
 *              11.1, 11.2, 11.3, 12.3, 12.5
 */
export default function DashboardCompliance() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { projectId: routeProjectId, taskId: routeTaskId } = useParams<{ projectId: string; taskId?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(projectReducer, initialProjectStore);
  const { user } = useAuth();
  const complianceCheck = useComplianceCheck();
  const remix = useComplianceRemix();

  // Read restored task state passed from task-detail.tsx navigation
  const restoredState = location.state as {
    restoredTaskId?: string;
    restoredStep?: string;
    restoredResult?: ComplianceResult;
    restoredMediaType?: string;
  } | null;

  // Task history for this project (fetched from API)
  const [taskHistory, setTaskHistory] = useState<{ check_id: string; media_type: string; risk_band: string | null; status: string; created_at: string }[]>([]);

  // Track the current task ID for step state persistence
  const currentTaskIdRef = useRef<string | null>(null);

  // Restore task state when navigated from task-detail.tsx
  useEffect(() => {
    if (!restoredState?.restoredResult || !restoredState.restoredTaskId) return;

    const { restoredTaskId, restoredStep, restoredResult, restoredMediaType } = restoredState;
    const id = routeProjectId ?? restoredTaskId;

    // Build a project from the restored state
    const restoredProject: Project = {
      id,
      campaignName: restoredResult.check_id ?? restoredTaskId,
      mediaType: (restoredMediaType ?? "image") as Project["mediaType"],
      currentStep: (restoredStep as Project["currentStep"]) ?? "review",
      completedSteps: ["upload", "check"],
      uploadParams: { market: restoredResult.market ?? "malaysia", ethnicity: "malay", ageGroup: "all_ages" },
      result: restoredResult,
      remixResult: null,
      error: null,
      createdAt: Date.now(),
    };

    dispatch({ type: "CREATE_PROJECT", payload: restoredProject });
    currentTaskIdRef.current = restoredTaskId;
  }, []); // run once on mount

  // Fetch task history on mount for project-scoped routes
  useEffect(() => {
    if (!routeProjectId) return;
    fetch(`${API_BASE}/api/projects/${routeProjectId}/checks`)
      .then((res) => res.ok ? res.json() : [])
      .then((data) => setTaskHistory(data))
      .catch(() => setTaskHistory([]));
  }, [routeProjectId]);

  // Persist workflow step state to Supabase tasks.pipeline_state
  const persistStepState = useCallback(async (
    taskId: string,
    step: string,
    result: ComplianceResult | null,
    status: string = "checked",
    remixResult: unknown = null
  ) => {
    if (!routeProjectId || !taskId) return;
    try {
      await savePipeline(routeProjectId, taskId, {
        nodes: [],
        edges: [],
        viewport: { panX: 0, panY: 0, zoom: 1 },
        // @ts-ignore — extending PipelineState for compliance use
        compliance_step: step,
        compliance_result: result,
        compliance_remix: remixResult,
        compliance_status: status,
      });
    } catch {
      // Non-fatal
    }
  }, [routeProjectId]);

  // "New Check" resets to upload step
  const handleNewCheck = useCallback(() => {
    currentTaskIdRef.current = null;
    dispatch({ type: "SET_ACTIVE_PROJECT", projectId: null as unknown as string });
  }, []);

  // Derive active project from state
  const activeProject: Project | null = state.activeProjectId
    ? state.projects.get(state.activeProjectId) ?? null
    : null;

  // Convert Map to sorted array for sidebar (newest first)
  const projectList = Array.from(state.projects.values());

  // Sidebar visibility: show when projects exist OR active project is past upload step
  const showSidebar = projectList.length > 0;

  // ─── Step transition animation ──────────────────────────────────────────────
  useGSAP(
    () => {
      const tl = gsap.timeline();
      // Only animate outgoing if the element exists (not on initial render)
      const outgoing = containerRef.current?.querySelector(".step-content-outgoing");
      if (outgoing) {
        tl.to(outgoing, { opacity: 0, y: -10, duration: 0.2 });
      }
      tl.from(".step-content-incoming", {
        opacity: 0,
        y: 20,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [activeProject?.currentStep] }
  );

  // ─── Submit flow ────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (params: UploadParams) => {
      const id = routeProjectId || generateId();
      const newProject: Project = {
        id,
        campaignName: params.file?.name?.replace(/\.[^/.]+$/, "") ?? "Text Ad",
        mediaType: deriveMediaType(params),
        currentStep: "check",
        completedSteps: [],
        uploadParams: params,
        result: null,
        remixResult: null,
        error: null,
        createdAt: Date.now(),
      };

      dispatch({ type: "CREATE_PROJECT", payload: newProject });

      try {
        const result: ComplianceResult = await complianceCheck.submit({
          ...params,
          projectId: id,
          username: user?.profile?.email ?? "anonymous",
        } as UploadParams & { projectId: string });
        dispatch({ type: "SET_RESULT", projectId: id, result });

        // Persist step state — find the task that was just created
        if (routeProjectId) {
          try {
            const tasksRes = await fetch(`${API_BASE}/api/projects/${routeProjectId}/tasks`);
            if (tasksRes.ok) {
              const tasks = await tasksRes.json();
              const latestTask = tasks[0]; // ordered by created_at desc
              if (latestTask?.id) {
                currentTaskIdRef.current = latestTask.id;
                // Update URL to include the task ID
                window.history.replaceState(null, "", `/dashboard/project/${routeProjectId}/compliance/${latestTask.id}`);
                await persistStepState(latestTask.id, "review", result, "reviewed");
              }
            }
          } catch {
            // Non-fatal
          }
        }
      } catch (err) {
        dispatch({
          type: "SET_ERROR",
          projectId: id,
          error: {
            step: "check",
            message: (err as Error).message || "Compliance check failed",
            retryable: true,
          },
        });
      }
    },
    [complianceCheck, routeProjectId, user, persistStepState]
  );

  // ─── Remix flow ─────────────────────────────────────────────────────────────
  const handleStartRemix = useCallback(async () => {
    if (!activeProject?.result) return;

    dispatch({
      type: "ADVANCE_STEP",
      projectId: activeProject.id,
      to: "remix",
    });

    try {
      await remix.startRemix(activeProject.result.check_id);
      dispatch({
        type: "SET_REMIX_RESULT",
        projectId: activeProject.id,
        remixResult: remix,
      });
    } catch (err) {
      dispatch({
        type: "SET_ERROR",
        projectId: activeProject.id,
        error: {
          step: "remix",
          message: (err as Error).message || "Remix failed",
          retryable: true,
        },
      });
    }
  }, [activeProject, remix]);

  // ─── Retry flow ─────────────────────────────────────────────────────────────
  const handleRetry = useCallback(() => {
    if (!activeProject?.error) return;

    dispatch({ type: "CLEAR_ERROR", projectId: activeProject.id });

    if (activeProject.error.step === "check") {
      handleSubmit(activeProject.uploadParams);
    } else if (activeProject.error.step === "remix") {
      handleStartRemix();
    }
  }, [activeProject, handleSubmit, handleStartRemix]);

  // ─── Step content rendering ─────────────────────────────────────────────────
  function renderStepContent() {
    if (!activeProject) {
      return (
        <div className="step-content-incoming">
          <UploadStep
            onSubmit={handleSubmit}
            isSubmitting={complianceCheck.isStreaming}
            error={null}
            onRetry={handleRetry}
          />
        </div>
      );
    }

    switch (activeProject.currentStep) {
      case "upload":
        return (
          <div className="step-content-incoming">
            <UploadStep
              onSubmit={handleSubmit}
              isSubmitting={complianceCheck.isStreaming}
              error={
                activeProject.error
                  ? {
                      message: activeProject.error.message,
                      retryable: activeProject.error.retryable,
                    }
                  : null
              }
              onRetry={handleRetry}
            />
          </div>
        );

      case "check":
        return (
          <div className="step-content-incoming">
            <CheckStep
              nodeStatuses={complianceCheck.nodeStatuses}
              currentNode={complianceCheck.currentNode}
              isStreaming={complianceCheck.isStreaming}
              mediaType={activeProject.mediaType}
              error={
                activeProject.error
                  ? {
                      message: activeProject.error.message,
                      retryable: activeProject.error.retryable,
                    }
                  : null
              }
              onRetry={handleRetry}
            />
          </div>
        );

      case "review":
        return activeProject.result ? (
          <div className="step-content-incoming">
            <ReviewStep
              result={activeProject.result}
              onStartRemix={handleStartRemix}
              isRemixAvailable={true}
            />
          </div>
        ) : null;

      case "remix":
        return (
          <div className="step-content-incoming">
            <RemixStep
              remixNodes={remix.remixNodes}
              isRemixing={remix.isRemixing}
              remixComplete={remix.remixComplete}
              remixError={activeProject.error?.message ?? null}
              onRetry={handleRetry}
            />
          </div>
        );

      case "compare":
        return activeProject.result ? (
          <div className="step-content-incoming">
            <ComparisonView
              originalResult={activeProject.result}
              remixResult={activeProject.remixResult}
            />
          </div>
        ) : null;
    }
  }

  // ─── Layout ─────────────────────────────────────────────────────────────────
  return (
    <div ref={containerRef} className="flex h-full gap-4">
      {/* Left panel — sidebar with task history + new check button */}
      <div className="w-64 shrink-0 flex flex-col gap-2">
        {/* All Tasks + New Check buttons */}
        {routeProjectId && (
          <>
            <button
              onClick={() => navigate(`/dashboard/project/${routeProjectId}`)}
              className="mx-2 mt-2 flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-text-muted hover:text-accent-blue transition-colors"
            >
              ← All Tasks
            </button>
            <button
              onClick={handleNewCheck}
              className="mx-2 flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-outline-variant px-3 py-2 text-xs font-semibold text-text-muted hover:border-accent-blue hover:text-accent-blue transition-colors"
            >
              + New Check
            </button>
          </>
        )}

        {/* Task history from API */}
        {taskHistory.length > 0 && (
          <div className="px-2 py-1">
            <p className="text-[10px] font-bold uppercase text-text-muted tracking-wider mb-1.5">Previous Checks</p>
            <div className="space-y-1 max-h-[200px] overflow-y-auto">
              {taskHistory.map((task) => (
                <div
                  key={task.check_id}
                  className="flex items-center gap-2 px-2 py-1.5 rounded text-xs text-text-muted bg-surface-inset/50 hover:bg-surface-inset cursor-default"
                >
                  <span className={`h-2 w-2 rounded-full shrink-0 ${
                    task.risk_band === "Critical" || task.risk_band === "High" ? "bg-red-500" :
                    task.risk_band === "Moderate" ? "bg-amber-500" : "bg-emerald-500"
                  }`} />
                  <span className="truncate flex-1">{task.media_type} • {task.status}</span>
                  <span className="text-[10px] shrink-0">{new Date(task.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Current session sidebar */}
        {showSidebar && (
          <ProjectSidebar
            projects={projectList}
            activeProjectId={state.activeProjectId}
            onSelectProject={(id) =>
              dispatch({ type: "SET_ACTIVE_PROJECT", projectId: id })
            }
          />
        )}
      </div>

      <div className="flex-1 flex flex-col gap-4">
        {/* Step Navigator — visible when a project is active */}
        {activeProject && (
          <StepNavigator
            steps={WORKFLOW_STEPS}
            currentStep={activeProject.currentStep}
            completedSteps={activeProject.completedSteps}
            onStepClick={(step) =>
              dispatch({
                type: "NAVIGATE_TO_STEP",
                projectId: activeProject.id,
                step,
              })
            }
          />
        )}

        {/* Main content area with step transition animations */}
        <div className="step-content flex-1">{renderStepContent()}</div>
      </div>
    </div>
  );
}
