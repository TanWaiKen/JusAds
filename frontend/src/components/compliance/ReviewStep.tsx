import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { ComplianceResult, Violation } from "@/services/complianceApi";
import { ViolationClipPlayer } from "@/components/compliance/ViolationClipPlayer";
import { Button } from "@/components/ui/button";

gsap.registerPlugin(useGSAP);

interface ReviewStepProps {
  result: ComplianceResult;
  onStartRemix: () => void;
  isRemixAvailable: boolean;
}

/**
 * Returns the Tailwind text color class for a given risk level.
 */
function getRiskLevelColor(riskLevel: string): string {
  switch (riskLevel) {
    case "High":
      return "text-red-500";
    case "Medium":
      return "text-amber-500";
    case "Low":
      return "text-emerald-500";
    default:
      return "text-text-muted";
  }
}

/**
 * Returns the severity badge styling based on severity level.
 */
function getSeverityBadgeClasses(severity: string): string {
  switch (severity.toLowerCase()) {
    case "error":
    case "critical":
    case "high":
      return "bg-error-container text-on-error-container";
    case "warning":
    case "medium":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300";
    default:
      return "bg-surface-inset text-text-muted";
  }
}

/**
 * Returns the border color class for a violation based on severity.
 */
function getSeverityBorderColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "error":
    case "critical":
    case "high":
      return "border-red-500";
    case "warning":
    case "medium":
      return "border-amber-500";
    default:
      return "border-outline-variant";
  }
}

/**
 * ReviewStep displays the compliance check results including:
 * - Animated compliance score (count-up from 0)
 * - Risk level with color coding
 * - Explanation text
 * - Staggered violation cards with clip players
 * - Success state when no violations
 * - Single Auto-Remix button when violations exist
 */
export function ReviewStep({
  result,
  onStartRemix,
  isRemixAvailable,
}: ReviewStepProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      // Score count-up animation
      gsap.to(".score-value", {
        textContent: result.score,
        duration: 1.5,
        snap: { textContent: 1 },
        ease: "power2.out",
      });

      // Staggered violation card entrance
      gsap.from(".violation-card", {
        y: 20,
        opacity: 0,
        stagger: 0.08,
        duration: 0.35,
        ease: "power2.out",
      });
    },
    { scope: containerRef }
  );

  const violations = result.violations ?? [];
  const hasViolations = violations.length > 0;

  return (
    <div ref={containerRef} className="flex flex-col gap-6 py-6 w-full max-w-3xl mx-auto">
      {/* Score and Risk Level Header */}
      <div className="bg-surface-card rounded-xl p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
        <div className="flex items-center justify-between mb-4">
          {/* Score Display */}
          <div className="flex items-center gap-4">
            <div className="flex flex-col items-center">
              <span className="text-code-xs font-code-xs text-text-muted uppercase tracking-wider">
                Compliance Score
              </span>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="score-value text-4xl font-bold text-text-primary">
                  0
                </span>
                <span className="text-lg text-text-muted">/100</span>
              </div>
            </div>
          </div>

          {/* Risk Level */}
          <div className="flex flex-col items-end">
            <span className="text-code-xs font-code-xs text-text-muted uppercase tracking-wider">
              Risk Level
            </span>
            <span
              className={`text-xl font-bold mt-1 ${getRiskLevelColor(result.risk_level)}`}
            >
              {result.risk_level}
            </span>
          </div>
        </div>

        {/* Explanation */}
        <p className="text-body-md font-body-md text-text-muted leading-relaxed">
          {result.explanation}
        </p>
      </div>

      {/* Success State — no violations */}
      {!hasViolations && (
        <div className="bg-surface-card rounded-xl p-8 shadow-[0_0_0_1px_rgba(0,0,0,0.08)] flex flex-col items-center justify-center text-center gap-3">
          <span
            className="material-symbols-outlined text-[48px] text-emerald-500"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            check_circle
          </span>
          <p className="font-label-ui text-label-ui text-text-primary font-bold">
            All checks passed
          </p>
          <p className="text-code-xs font-code-xs text-text-muted">
            This asset meets all compliance requirements. No violations detected.
          </p>
        </div>
      )}

      {/* Violations List */}
      {hasViolations && (
        <div className="flex flex-col gap-3">
          <h3 className="font-headline-sm text-text-primary text-[16px]">
            Violations ({violations.length})
          </h3>

          {violations.map((violation: Violation) => (
            <div
              key={violation.index}
              className={`violation-card p-4 bg-surface-card rounded-xl shadow-[0_0_0_1px_rgba(0,0,0,0.08)] border-l-4 ${getSeverityBorderColor(violation.severity)}`}
            >
              {/* Header: category + severity badge + type */}
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <h4 className="font-code-xs text-code-xs font-bold text-text-primary uppercase">
                  {violation.category}
                </h4>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${getSeverityBadgeClasses(violation.severity)}`}
                >
                  {violation.severity}
                </span>
                <span className="text-code-xs font-code-xs text-text-muted capitalize">
                  {violation.type}
                </span>
              </div>

              {/* Description */}
              <p className="text-text-muted text-[13px] leading-relaxed mb-3">
                {violation.description}
              </p>

              {/* Clip Player — only when clip_url is non-null */}
              {violation.clip_url && (
                <ViolationClipPlayer
                  clipUrl={violation.clip_url}
                  start={violation.start}
                  end={violation.end}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Auto-Remix Button — only when violations exist */}
      {hasViolations && isRemixAvailable && (
        <div className="flex justify-center pt-2">
          <Button
            variant="default"
            size="lg"
            onClick={onStartRemix}
            className="gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">
              auto_fix_high
            </span>
            Auto-Remix
          </Button>
        </div>
      )}
    </div>
  );
}
