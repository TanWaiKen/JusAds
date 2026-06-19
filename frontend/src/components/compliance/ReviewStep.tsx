import { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { ComplianceResult } from "@/services/complianceApi";
import { normalizeViolations } from "@/services/complianceApi";
import type { Violation } from "@/services/complianceApi";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/services/complianceApi";

gsap.registerPlugin(useGSAP);

interface ReviewStepProps {
  result: ComplianceResult;
  onStartRemix: () => void;
  isRemixAvailable: boolean;
}

function getRiskLevelColor(riskLevel: string): string {
  switch (riskLevel) {
    case "Critical": return "text-red-600";
    case "High": return "text-red-500";
    case "Medium": case "Moderate": return "text-amber-500";
    case "Low": return "text-emerald-500";
    default: return "text-text-muted";
  }
}

function getRiskBarColor(percentage: number): string {
  if (percentage >= 75) return "bg-red-500";
  if (percentage >= 50) return "bg-amber-500";
  if (percentage >= 25) return "bg-orange-400";
  return "bg-emerald-500";
}

function getSeverityBadgeClasses(severity: string): string {
  switch (severity.toLowerCase()) {
    case "error": case "critical": case "high":
      return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300";
    case "warning": case "medium":
      return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300";
    default:
      return "bg-surface-inset text-text-muted";
  }
}

function getSeverityBorderColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "error": case "critical": case "high": return "border-red-500";
    case "warning": case "medium": return "border-amber-500";
    default: return "border-outline-variant";
  }
}

function formatSeconds(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

type ImageTab = "original" | "segmented" | "remix";

export function ReviewStep({ result, onStartRemix, isRemixAvailable }: ReviewStepProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<ImageTab>("segmented");

  // Derive common values
  const riskPercentage = result.risk_percentage ?? (result.score != null ? 100 - result.score : 0);
  const riskLevel = result.risk_level ?? result.risk_band ?? "Unknown";
  const explanation = result.explanation ?? "";
  const suggestion = result.suggestion;
  const highRiskIndicators = result.high_risk_indicator ?? result.high_risk_indicators;
  const localizationPlan = result.localization_plan;
  const verification = result.verification;
  const mediaType = result.video_filename ? "video" : (result.market ? "unknown" : "text");

  // Image URLs (stored as public S3 URLs)
  const segmentedUrl = result.s3_segmented_key || null;
  const originalUrl = result.s3_upload_key || null;
  const remixUrl = result.s3_remix_key || null;
  const hasAnyImage = !!(originalUrl || segmentedUrl || remixUrl);

  // Video violations timeline (for video type)
  const violationsTimeline = result.violations_timeline ?? [];
  const hasVideoClips = violationsTimeline.length > 0 && violationsTimeline.some(
    (v) => typeof v === "object" && v !== null && "start_seconds" in v
  );

  // Normalized violations
  const violations = normalizeViolations(result);
  const hasViolations = violations.length > 0 || (highRiskIndicators && highRiskIndicators.length > 0);

  useGSAP(
    () => {
      gsap.from(".risk-bar-fill", { scaleX: 0, transformOrigin: "left", duration: 1.2, ease: "power2.out" });

      const counter = { val: 0 };
      gsap.to(counter, {
        val: riskPercentage,
        duration: 1.5,
        ease: "power2.out",
        onUpdate: () => {
          const el = containerRef.current?.querySelector(".risk-value");
          if (el) el.textContent = Math.round(counter.val).toString();
        },
      });

      const cards = containerRef.current?.querySelectorAll(".result-card");
      if (cards && cards.length > 0) {
        gsap.from(cards, { y: 20, opacity: 0, stagger: 0.08, duration: 0.35, ease: "power2.out" });
      }
    },
    { scope: containerRef, dependencies: [riskPercentage] }
  );

  return (
    <div ref={containerRef} className="flex flex-col gap-5 py-6 w-full max-w-3xl mx-auto">
      {/* Risk Score Header */}
      <div className="result-card bg-surface-card rounded-xl p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex flex-col">
            <span className="text-code-xs text-text-muted uppercase tracking-wider">Risk Percentage</span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className={`risk-value text-4xl font-bold ${getRiskLevelColor(riskLevel)}`}>0</span>
              <span className="text-lg text-text-muted">%</span>
            </div>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-code-xs text-text-muted uppercase tracking-wider">Risk Level</span>
            <span className={`text-xl font-bold mt-1 ${getRiskLevelColor(riskLevel)}`}>{riskLevel}</span>
          </div>
        </div>
        <div className="w-full h-3 bg-surface-inset rounded-full overflow-hidden">
          <div className={`risk-bar-fill h-full rounded-full ${getRiskBarColor(riskPercentage)}`} style={{ width: `${riskPercentage}%` }} />
        </div>
        {explanation && <p className="mt-4 text-[13px] text-text-muted leading-relaxed">{explanation}</p>}
      </div>

      {/* Image Viewer — for image/video media types with S3 URLs */}
      {hasAnyImage && (
        <div className="result-card bg-surface-card rounded-xl overflow-hidden shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex border-b border-outline-variant">
            {originalUrl && (
              <button
                className={`flex-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${activeTab === "original" ? "text-accent-blue border-b-2 border-accent-blue bg-accent-blue/5" : "text-text-muted hover:text-text-primary"}`}
                onClick={() => setActiveTab("original")}
              >
                Original
              </button>
            )}
            {segmentedUrl && (
              <button
                className={`flex-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${activeTab === "segmented" ? "text-accent-blue border-b-2 border-accent-blue bg-accent-blue/5" : "text-text-muted hover:text-text-primary"}`}
                onClick={() => setActiveTab("segmented")}
              >
                Segmented
              </button>
            )}
            {remixUrl && (
              <button
                className={`flex-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${activeTab === "remix" ? "text-accent-blue border-b-2 border-accent-blue bg-accent-blue/5" : "text-text-muted hover:text-text-primary"}`}
                onClick={() => setActiveTab("remix")}
              >
                Remix
              </button>
            )}
          </div>
          <div className="p-4 flex items-center justify-center min-h-[200px] bg-black/5 dark:bg-white/5">
            {activeTab === "original" && originalUrl && <img src={originalUrl} alt="Original" className="max-h-[400px] max-w-full object-contain rounded" />}
            {activeTab === "segmented" && segmentedUrl && <img src={segmentedUrl} alt="Segmented analysis" className="max-h-[400px] max-w-full object-contain rounded" />}
            {activeTab === "remix" && remixUrl && <img src={remixUrl} alt="Remixed" className="max-h-[400px] max-w-full object-contain rounded" />}
          </div>
        </div>
      )}

      {/* Video Violations Timeline — for video media type */}
      {hasVideoClips && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-3">
            Violations Timeline ({violationsTimeline.length})
          </h3>
          <div className="space-y-2">
            {violationsTimeline.map((v, i) => {
              const item = v as Record<string, unknown>;
              const start = item.start_seconds as number | undefined;
              const end = item.end_seconds as number | undefined;
              const type = (item.type as string) ?? "visual";
              const desc = (item.description as string) ?? (item.region_description as string) ?? "";
              const clipUrl = item.clip_url as string | undefined;

              return (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-surface-inset/50 border-l-4 border-amber-500">
                  {start != null && end != null && (
                    <span className="shrink-0 text-code-xs font-mono text-accent-blue bg-accent-blue/10 px-2 py-0.5 rounded">
                      {formatSeconds(start)} – {formatSeconds(end)}
                    </span>
                  )}
                  <div className="flex-1">
                    <span className="text-code-xs text-text-muted uppercase mr-2">{type}</span>
                    <span className="text-[13px] text-text-muted">{desc}</span>
                  </div>
                  {clipUrl && (
                    <a
                      href={clipUrl.startsWith("http") ? clipUrl : `${API_BASE}${clipUrl}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 text-xs text-accent-blue hover:underline"
                    >
                      Play clip
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Region-based violations (image type without timestamps) */}
      {!hasVideoClips && violationsTimeline.length > 0 && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-3">
            Violation Regions ({violationsTimeline.length})
          </h3>
          <div className="space-y-2">
            {violationsTimeline.map((v, i) => {
              const item = v as Record<string, unknown>;
              const type = (item.type as string) ?? "visual";
              const desc = (item.region_description as string) ?? (item.description as string) ?? "";
              return (
                <div key={i} className="flex items-center gap-2 p-2 rounded bg-surface-inset/50">
                  <span className="text-code-xs text-text-muted uppercase bg-surface-inset px-1.5 py-0.5 rounded">{type}</span>
                  <span className="text-[13px] text-text-muted">{desc}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* High Risk Indicators */}
      {highRiskIndicators && highRiskIndicators.length > 0 && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-3">
            High Risk Indicators ({highRiskIndicators.length})
          </h3>
          <ul className="space-y-2">
            {highRiskIndicators.map((indicator, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-red-500" />
                <span className="text-[13px] text-text-muted">{indicator}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Normalized Violations (from normalizeViolations) */}
      {violations.length > 0 && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-3">Violations ({violations.length})</h3>
          <div className="space-y-3">
            {violations.map((violation: Violation, i) => (
              <div key={i} className={`p-3 rounded-lg border-l-4 bg-surface-inset/50 ${getSeverityBorderColor(violation.severity)}`}>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${getSeverityBadgeClasses(violation.severity)}`}>{violation.severity}</span>
                  <span className="text-code-xs text-text-muted capitalize">{violation.type}</span>
                </div>
                <p className="text-[13px] text-text-muted leading-relaxed">{violation.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Verification */}
      {verification && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-3">Verification</h3>
          <div className="flex items-center gap-4 text-[13px] text-text-muted mb-3">
            <span>Confidence: <strong className="text-text-primary">{verification.confidence}</strong></span>
            <span>Confirmed: <strong className="text-text-primary">{verification.confirmed_ratio}</strong></span>
          </div>
          {verification.verified && verification.verified.length > 0 && (
            <div className="space-y-2">
              {verification.verified.map((v, i) => (
                <div key={i} className="flex items-start gap-2 text-[12px]">
                  <span className={`mt-0.5 shrink-0 ${v.confirmed ? "text-emerald-500" : "text-red-500"}`}>
                    {v.confirmed ? "✓" : "✗"}
                  </span>
                  <div>
                    <span className="text-text-muted">{v.violation}</span>
                    {v.sources && v.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {v.sources.map((src, j) => (
                          <a key={j} href={src} target="_blank" rel="noopener noreferrer" className="text-accent-blue hover:underline truncate max-w-[200px]">[{j + 1}]</a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Suggestion */}
      {suggestion && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-2">Suggestion</h3>
          <p className="text-[13px] text-text-muted leading-relaxed">{suggestion}</p>
        </div>
      )}

      {/* Localization Plan */}
      {localizationPlan && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-bold text-text-primary mb-2">Localization Plan</h3>
          <p className="text-[13px] text-text-muted leading-relaxed">{localizationPlan}</p>
        </div>
      )}

      {/* No Issues */}
      {!hasViolations && (
        <div className="result-card bg-surface-card rounded-xl p-8 shadow-[0_0_0_1px_rgba(0,0,0,0.08)] flex flex-col items-center justify-center text-center gap-3">
          <div className="h-12 w-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
            <svg className="h-6 w-6 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="font-bold text-text-primary">All checks passed</p>
          <p className="text-code-xs text-text-muted">This asset meets all compliance requirements.</p>
        </div>
      )}

      {/* Auto-Remix Button */}
      {hasViolations && isRemixAvailable && (
        <div className="flex justify-center pt-2">
          <Button variant="default" size="lg" onClick={onStartRemix} className="gap-2">
            Auto-Remix
          </Button>
        </div>
      )}
    </div>
  );
}
