import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { ComplianceResult, Violation } from "@/services/complianceApi";
import { ViolationClipPlayer } from "@/components/compliance/ViolationClipPlayer";

gsap.registerPlugin(useGSAP);

interface ComparisonViewProps {
  originalResult: ComplianceResult;
  remixResult: unknown | null;
  mediaType: "text" | "image" | "audio" | "video";
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
  if (!remixResult || typeof remixResult !== "object") return null;

  const result = remixResult as Record<string, unknown>;

  // New hook state shape
  if (result.imageEditResult && typeof result.imageEditResult === "object") {
    const editResult = result.imageEditResult as Record<string, unknown>;
    if (typeof editResult.quality_score === "number") {
      return editResult.quality_score;
    }
  }

  // Legacy shape support
  if ("score" in result && typeof result.score === "number") {
    return result.score;
  }
  if ("quality_score" in result && typeof result.quality_score === "number") {
    return result.quality_score;
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
export function ComparisonView({ originalResult, remixResult, mediaType }: ComparisonViewProps) {
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

        {/* Media-type-specific original content preview */}
        {mediaType === "image" && originalResult.s3_upload_key && (
          <div className="mb-4 rounded-lg overflow-hidden bg-black/5 dark:bg-white/5">
            <img src={originalResult.s3_upload_key} alt="Original" className="max-h-[250px] w-full object-contain" />
          </div>
        )}
        {mediaType === "audio" && originalResult.s3_upload_key && (
          <div className="mb-4">
            <audio controls className="w-full" src={originalResult.s3_upload_key}>
              Your browser does not support the audio element.
            </audio>
          </div>
        )}
        {mediaType === "video" && originalResult.s3_upload_key && (
          <div className="mb-4 rounded-lg overflow-hidden bg-black/5 dark:bg-white/5">
            <video controls className="max-h-[250px] w-full" src={originalResult.s3_upload_key}>
              Your browser does not support the video element.
            </video>
          </div>
        )}

        {/* Violations List */}
        {(originalResult.violations ?? []).length > 0 ? (
          <div className="space-y-3">
            <p className="text-label-ui font-label-ui text-text-muted">
              {originalResult.violations.length} violation{originalResult.violations.length !== 1 ? "s" : ""} found
            </p>
            {(originalResult.violations ?? []).map((violation: Violation) => (
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

      {/* Right Panel: Outcome / Remixed Version */}
      <section
        aria-label="Remix outcome"
        className="remixed-panel bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]"
      >
        {(() => {
          const res = remixResult as Record<string, unknown> | null;
          const outcome = res?.remixOutcome as string | undefined;

          // OUTCOME: CANNOT_FIX
          if (outcome === "cannot_fix") {
            const cannotFixData = res?.cannotFixData as Record<string, unknown> | undefined;
            return (
              <>
                <h3 className="font-headline-sm text-text-primary mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-[20px] text-amber-500">warning</span>
                  Manual Fix Required
                </h3>
                <div className="flex flex-col gap-3 p-4 bg-amber-500/10 rounded-xl border border-amber-500/20">
                  <p className="text-text-body text-sm">
                    {cannotFixData?.guidance as string || "This image cannot be automatically fixed. Please edit manually or provide a new image."}
                  </p>
                  {!!cannotFixData?.reasoning && (
                    <p className="text-text-muted text-xs bg-surface-inset p-2 rounded-lg mt-1 border border-outline-variant">
                      {String(cannotFixData.reasoning)}
                    </p>
                  )}
                </div>
              </>
            );
          }

          // OUTCOME: EDIT_FAILED
          if (outcome === "edit_failed") {
            const editFailedData = res?.editFailedData as Record<string, unknown> | undefined;
            return (
              <>
                <h3 className="font-headline-sm text-text-primary mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-[20px] text-error-container">error</span>
                  Edit Failed
                </h3>
                <div className="flex flex-col gap-3 p-4 bg-error-container/80 rounded-xl border border-error-container">
                  <p className="text-sm text-on-error-container">
                    {editFailedData?.fallback_guidance as string || "The AI edit process failed."}
                  </p>
                  {!!editFailedData?.error && (
                    <p className="text-xs text-on-error-container/80 mt-2 bg-on-error-container/10 p-2 rounded-lg">
                      Error: {String(editFailedData.error)}
                    </p>
                  )}
                </div>
              </>
            );
          }

          // OUTCOME: COMPLIANT or IMAGE_EDIT or LEGACY SUCCESS
          return (
            <>
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

              {/* Media-type-specific remixed content preview */}
              {mediaType === "image" && (
                (() => {
                  let remixUrl = originalResult.s3_remix_key;
                  if (res?.imageEditResult && typeof res.imageEditResult === "object") {
                    const editResult = res.imageEditResult as Record<string, unknown>;
                    if (typeof editResult.s3_remix_url === "string") {
                      remixUrl = editResult.s3_remix_url;
                    }
                  }
                  return remixUrl ? (
                    <div className="mb-4 rounded-lg overflow-hidden bg-black/5 dark:bg-white/5">
                      <img src={remixUrl} alt="Remixed" className="max-h-[250px] w-full object-contain" />
                    </div>
                  ) : null;
                })()
              )}
              {mediaType === "audio" && originalResult.s3_remix_key && (
                <div className="mb-4">
                  <audio controls className="w-full" src={originalResult.s3_remix_key}>
                    Your browser does not support the audio element.
                  </audio>
                </div>
              )}
              {mediaType === "video" && originalResult.s3_remix_key && (
                <div className="mb-4 rounded-lg overflow-hidden bg-black/5 dark:bg-white/5">
                  <video controls className="max-h-[250px] w-full" src={originalResult.s3_remix_key}>
                    Your browser does not support the video element.
                  </video>
                </div>
              )}

              {/* Remixed Result Details */}
              <div className="space-y-3">
                {res ? (
                  <div className="p-3 bg-surface-panel rounded-lg">
                    <p className="text-code-xs font-code-xs text-text-muted uppercase mb-2">
                      Remix Details
                    </p>
                    {outcome === "compliant" ? (
                      <p className="text-text-primary text-[12px] leading-relaxed">
                        The original image is fully compliant and does not require any edits.
                      </p>
                    ) : (
                      <p className="text-text-primary text-[12px] leading-relaxed">
                        All violations have been addressed. The remixed version meets compliance standards.
                      </p>
                    )}
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
            </>
          );
        })()}
      </section>
    </div>
  );
}
