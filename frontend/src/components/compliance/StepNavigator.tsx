import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

import type { StepDefinition, WorkflowStep } from "@/types/compliance";

gsap.registerPlugin(useGSAP);

interface StepNavigatorProps {
  steps: readonly StepDefinition[];
  currentStep: WorkflowStep;
  completedSteps: WorkflowStep[];
  onStepClick: (step: WorkflowStep) => void;
}

/**
 * Horizontal step navigator for the compliance workflow.
 * Displays Upload → Check → Review → Remix → Compare steps with
 * keyboard navigation, ARIA attributes, and GSAP animation.
 */
export function StepNavigator({
  steps,
  currentStep,
  completedSteps,
  onStepClick,
}: StepNavigatorProps) {
  const containerRef = useRef<HTMLElement>(null);
  const indicatorRef = useRef<HTMLDivElement>(null);

  // Animate active indicator on step change
  useGSAP(
    () => {
      if (!indicatorRef.current) return;

      const activeIndex = steps.findIndex((s) => s.id === currentStep);
      if (activeIndex === -1) return;

      // Find the active button to position the indicator
      const activeButton = containerRef.current?.querySelector(
        `[data-step="${currentStep}"]`
      ) as HTMLElement | null;

      if (!activeButton) return;

      const containerRect = containerRef.current!.getBoundingClientRect();
      const buttonRect = activeButton.getBoundingClientRect();
      const targetX = buttonRect.left - containerRect.left;

      gsap.to(indicatorRef.current, {
        x: targetX,
        opacity: 1,
        duration: 0.3,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [currentStep] }
  );

  function getStepState(
    stepId: WorkflowStep
  ): "active" | "completed" | "unreached" {
    if (stepId === currentStep) return "active";
    if (completedSteps.includes(stepId)) return "completed";
    return "unreached";
  }

  function getStepStyles(state: "active" | "completed" | "unreached"): string {
    switch (state) {
      case "active":
        return "text-text-primary border-primary bg-surface-panel";
      case "completed":
        return "text-text-secondary border-border-default bg-surface-container hover:bg-surface-container-high cursor-pointer";
      case "unreached":
        return "text-text-muted border-border-subtle bg-surface-container opacity-50 cursor-not-allowed";
    }
  }

  function handleStepClick(stepId: WorkflowStep) {
    const state = getStepState(stepId);
    if (state === "completed") {
      onStepClick(stepId);
    }
  }

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    stepId: WorkflowStep
  ) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleStepClick(stepId);
    }
  }

  return (
    <nav ref={containerRef} aria-label="Compliance workflow steps">
      <ol role="list" className="relative flex items-center gap-2">
        {/* Active step indicator underline */}
        <div
          ref={indicatorRef}
          className="absolute bottom-0 left-0 h-0.5 w-16 bg-primary rounded-full opacity-0"
          aria-hidden="true"
        />

        {steps.map((step, index) => {
          const state = getStepState(step.id);
          const isActive = state === "active";
          const isUnreached = state === "unreached";

          return (
            <li key={step.id} className="flex items-center">
              {index > 0 && (
                <div
                  className={`h-px w-4 mx-1 ${
                    state === "unreached"
                      ? "bg-border-subtle"
                      : "bg-border-default"
                  }`}
                  aria-hidden="true"
                />
              )}
              <button
                type="button"
                data-step={step.id}
                aria-current={isActive ? "step" : undefined}
                aria-disabled={isUnreached ? "true" : undefined}
                tabIndex={isUnreached ? -1 : 0}
                onClick={() => handleStepClick(step.id)}
                onKeyDown={(e) => handleKeyDown(e, step.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-label-ui font-label-ui transition-colors duration-200 ${getStepStyles(state)}`}
              >
                <span
                  className="material-symbols-outlined text-[18px]"
                  style={{ fontVariationSettings: "'FILL' 0" }}
                  aria-hidden="true"
                >
                  {step.icon}
                </span>
                <span>{step.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
