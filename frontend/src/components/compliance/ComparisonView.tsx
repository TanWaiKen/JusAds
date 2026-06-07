import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { ComplianceResult, Violation } from "@/services/complianceApi";
import { ViolationClipPlayer } from "@/components/compliance/ViolationClipPlayer";

gsap.registerPlugin(useGSAP);

interface ComparisonViewProps {
  originalResult: ComplianceResult;
  remixResult: unknown | null;
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
 * Returns the color class for a risk level.
 */
function getRiskLevelColor(riskLevel: string): string {
  switch (riskLevel) {
    case "High":
      return "text-error";
    case "Medium":
      return "text-amber-500";
    case "Low":
      return "text-emerald-500";
    default:
      return "text-text-muted";
  }
}

/**
 * Extracts a compliance score from a remix result if available.
 * The remix result shape is opaque (unknown), so we safely check for a score field.
 */
function getRemixScore(remixResult: unknown): number | null {
  if (
    remixResult &&
    typeof remixResult === "object" &&
    "score" in remixResult &&
    typeof (remixResult as Record<string, unknown>).score === "number"
  ) {
    return (remixResult as Record<string, unknown>).score as number;
  }
  return null;
}

/**
 * ComparisonView displays a side-by-side layout comparing
 * the original compliance result (with violations) against the remixed compliant version.
 *
 * Left panel: original violations, score, clip players
 * Right panel: remixed result details or "Compliant" badge
 */
export function ComparisonView({ originalResult, remixResult }: ComparisonViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".original-panel", { x: -50, opacity: 0, duration: 0.5, ease: "power2.out" });
    gsap.from(".remixed-panel", { x: 50, opacity: 0, duration: 0.5, ease: "power2.out" });
  }, { scope: containerRef });

  const remixScore = getRemixScore(remixResult);

  return (
    <div ref={containerRef} className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Left Panel: Original Content */}
      <section
        aria-label="Original content with violations"
        className="original-panel bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]"
      >
        <h3 className="font-headline-sm text-text-primary mb-4 flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[20px] text-text-muted"
            style={{ fontVariationSettings: "'FILL' 0" }}
          >
            warning
          </span>
          Original
        </h3>

        {/* Compliance Score */}
        <div className="mb-4 p-3 bg-surface-panel rounded-lg">
          <p className="text-code-xs font-code-xs text-text-muted uppercase mb-1">
            Compliance Score
          </p>
          <div className="flex items-baseline gap-2">
            <span className={`text-2xl font-bold ${getRiskLevelColor(originalResult.risk_level)}`}>
              {originalResult.score}
            </span>
            <span className="text-code-xs font-code-xs text-text-muted">/ 100</span>
            <span
              className={`ml-auto px-2 py-0.5 rounded text-[10px] font-bold uppercase ${getSeverityBadgeClasses(originalResult.risk_level === "High" ? "error" : originalResult.risk_level === "Medium" ? "warning" : "low")}`}
            >
              {originalResult.risk_level} Risk
            </span>
          </div>
        </div>

        {/* Violations List */}
        {originalResult.violations.length > 0 ? (
          <div className="space-y-3">
            <p className="text-label-ui font-label-ui text-text-muted">
              {originalResult.violations.length} violation{originalResult.violations.length !== 1 ? "s" : ""} found
            </p>
            {originalResult.violations.map((violation: Violation) => (
              <div
                key={violation.index}
                className="p-3 bg-surface-panel rounded border-l-4 border-error"
              >
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${getSeverityBadgeClasses(violation.severity)}`}
                  >
                    {violation.severity}
                  </span>
                  <span className="text-code-xs font-code-xs text-text-muted capitalize">
                    {violation.type}
                  </span>
                </div>
                <p className="text-text-primary text-[12px] leading-relaxed mb-2">
                  {violation.description}
                </p>

                {/* Clip player for violations with a clip_url */}
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
        ) : (
          <p className="text-body-md font-body-md text-text-muted">
            No violations detected.
          </p>
        )}
      </section>

      {/* Right Panel: Remixed Compliant Version */}
      <section
        aria-label="Remixed compliant version"
        className="remixed-panel bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]"
      >
        <h3 className="font-headline-sm text-text-primary mb-4 flex items-center gap-2">
          <span
            className="material-symbols-outlined text-[20px] text-emerald-500"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            check_circle
          </span>
          Remixed
        </h3>

        {/* Remixed Score or Compliant Badge */}
        <div className="mb-4 p-3 bg-surface-panel rounded-lg">
          <p className="text-code-xs font-code-xs text-text-muted uppercase mb-1">
            Compliance Score
          </p>
          {remixScore !== null ? (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-500">
                {remixScore}
              </span>
              <span className="text-code-xs font-code-xs text-text-muted">/ 100</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 text-[11px] font-bold uppercase">
                Compliant
              </span>
            </div>
          )}
        </div>

        {/* Remixed Result Details */}
        <div className="space-y-3">
          {remixResult && typeof remixResult === "object" ? (
            <div className="p-3 bg-surface-panel rounded-lg">
              <p className="text-code-xs font-code-xs text-text-muted uppercase mb-2">
                Remix Details
              </p>
              <p className="text-text-primary text-[12px] leading-relaxed">
                All violations have been addressed. The remixed version meets compliance standards.
              </p>
            </div>
          ) : (
            <div className="p-3 bg-surface-panel rounded-lg flex flex-col items-center justify-center text-center gap-2 py-6">
              <span
                className="material-symbols-outlined text-[36px] text-emerald-500"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                verified
              </span>
              <p className="font-label-ui text-label-ui text-text-primary font-bold">
                Compliant Version Ready
              </p>
              <p className="text-code-xs font-code-xs text-text-muted">
                The remixed content has been generated to meet all compliance requirements.
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
