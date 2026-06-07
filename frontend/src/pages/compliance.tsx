import { useReducer, useRef, useCallback } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useComplianceCheck } from "@/hooks/useComplianceCheck";
import { useComplianceRemix } from "@/hooks/useComplianceRemix";
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
  const [state, dispatch] = useReducer(projectReducer, initialProjectStore);
  const complianceCheck = useComplianceCheck();
  const remix = useComplianceRemix();

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
      tl.to(".step-content-outgoing", { opacity: 0, y: -10, duration: 0.2 })
        .from(".step-content-incoming", {
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
      const id = generateId();
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
        const result: ComplianceResult = await complianceCheck.submit(params);
        dispatch({ type: "SET_RESULT", projectId: id, result });
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
    [complianceCheck]
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
      {/* Sidebar — visible when projects exist */}
      {showSidebar && (
        <ProjectSidebar
          projects={projectList}
          activeProjectId={state.activeProjectId}
          onSelectProject={(id) =>
            dispatch({ type: "SET_ACTIVE_PROJECT", projectId: id })
          }
        />
      )}

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
