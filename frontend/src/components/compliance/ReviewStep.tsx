import { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { ComplianceResult } from "@/services/complianceApi";
import { normalizeViolations } from "@/services/complianceApi";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/services/complianceApi";
import { ExternalLink, ShieldCheck, Globe, FileText } from "lucide-react";

gsap.registerPlugin(useGSAP);

interface ReviewStepProps {
  result: ComplianceResult;
  onStartRemix: () => void;
  isRemixAvailable: boolean;
  mediaType: "text" | "image" | "audio" | "video";
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

function formatSeconds(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

/** Extract domain from a URL for display */
function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return url.slice(0, 30);
  }
}

type ImageTab = "original" | "segmented" | "remix";

export function ReviewStep({ result, onStartRemix, isRemixAvailable, mediaType }: ReviewStepProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Image URLs (only relevant for image media)
  const isImage = mediaType === "image";
  const segmentedUrl = isImage ? (result.s3_segmented_key || null) : null;
  const originalUrl = isImage ? (result.s3_upload_key || null) : null;
  const remixUrl = isImage ? (result.s3_remix_key || null) : null;
  const hasAnyImage = isImage && !!(originalUrl || segmentedUrl || remixUrl);

  // Default to first available tab
  const defaultTab: ImageTab = segmentedUrl ? "segmented" : originalUrl ? "original" : "remix";
  const [activeTab, setActiveTab] = useState<ImageTab>(defaultTab);

  console.log("[ReviewStep] result:", result);

  // Derive common values
  const riskPercentage = result.risk_percentage ?? (result.score != null ? 100 - result.score : 0);
  const riskLevel = result.risk_level ?? result.risk_band ?? "Unknown";
  const explanation = result.explanation ?? "";
  const suggestion = result.suggestion;
  const highRiskIndicators = result.high_risk_indicator ?? result.high_risk_indicators;
  const localizationPlan = result.localization_plan;
  const verification = result.verification;

  // Determine media type from prop (explicit from parent)
  const isAudio = mediaType === "audio";
  const isVideo = mediaType === "video";

  // Video violations
  const violationsTimeline = result.violations_timeline ?? [];

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
      {/* ═══ Risk Score ═══ */}
      <div className="result-card bg-surface-card rounded-xl p-6 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex flex-col">
            <span className="text-code-xs text-text-muted uppercase tracking-wider">Risk Percentage</span>
            <div className="flex items-baseline gap-1 mt-1">
              <span className={`risk-value text-4xl font-semibold ${getRiskLevelColor(riskLevel)}`}>0</span>
              <span className="text-lg text-text-muted">%</span>
            </div>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-code-xs text-text-muted uppercase tracking-wider">Risk Level</span>
            <span className={`text-xl font-semibold mt-1 ${getRiskLevelColor(riskLevel)}`}>{riskLevel}</span>
          </div>
        </div>
        <div className="w-full h-3 bg-surface-inset rounded-full overflow-hidden">
          <div className={`risk-bar-fill h-full rounded-full ${getRiskBarColor(riskPercentage)}`} style={{ width: `${riskPercentage}%` }} />
        </div>

        {/* ═══ Compliance Verdict Badge ═══ */}
        {(() => {
          const verdict = (result as unknown as Record<string, unknown>).compliance_verdict as string | undefined;
          if (!verdict) return null;
          const config = {
            accepted: { label: "Accepted", bg: "bg-emerald-500/10 border-emerald-500/30", text: "text-emerald-600" },
            needs_remediation: { label: "Needs Remediation", bg: "bg-amber-500/10 border-amber-500/30", text: "text-amber-600" },
            rejected: { label: "Rejected", bg: "bg-red-500/10 border-red-500/30", text: "text-red-600" },
          }[verdict] ?? { label: verdict, bg: "bg-surface-inset", text: "text-text-muted" };
          return (
            <div className={`mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg border ${config.bg}`}>
              <span className={`text-sm font-semibold ${config.text}`}>{config.label}</span>
            </div>
          );
        })()}

        {explanation && <p className="mt-4 text-[13px] text-text-muted leading-relaxed">{explanation}</p>}

        {/* ═══ Check Metadata: Market, Ethnicity, Age Group, Platform ═══ */}
        <div className="mt-4 flex flex-wrap gap-3">
          {result.market && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-inset/60">
              <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Market</span>
              <span className="text-xs font-medium text-text-primary capitalize">{result.market}</span>
            </div>
          )}
          {result.ethnicity && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-inset/60">
              <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Ethnicity</span>
              <span className="text-xs font-medium text-text-primary capitalize">{result.ethnicity}</span>
            </div>
          )}
          {result.age_group && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-inset/60">
              <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Age Group</span>
              <span className="text-xs font-medium text-text-primary capitalize">{result.age_group.replace(/_/g, " ")}</span>
            </div>
          )}
          {result.platform && result.platform !== "general" && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-inset/60">
              <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Platform</span>
              <span className="text-xs font-medium text-text-primary capitalize">{result.platform}</span>
            </div>
          )}
        </div>
      </div>

      {/* ═══ Image Viewer (Image media type) ═══ */}
      {hasAnyImage && (
        <div className="result-card bg-surface-card rounded-xl overflow-hidden shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex border-b border-outline-variant">
            {originalUrl && (
              <button className={`flex-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${activeTab === "original" ? "text-accent-blue border-b-2 border-accent-blue bg-accent-blue/5" : "text-text-muted hover:text-text-primary"}`} onClick={() => setActiveTab("original")}>Original</button>
            )}
            {segmentedUrl && (
              <button className={`flex-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${activeTab === "segmented" ? "text-accent-blue border-b-2 border-accent-blue bg-accent-blue/5" : "text-text-muted hover:text-text-primary"}`} onClick={() => setActiveTab("segmented")}>Segmented</button>
            )}
            {remixUrl && (
              <button className={`flex-1 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${activeTab === "remix" ? "text-accent-blue border-b-2 border-accent-blue bg-accent-blue/5" : "text-text-muted hover:text-text-primary"}`} onClick={() => setActiveTab("remix")}>Remix</button>
            )}
          </div>
          <div className="p-4 flex items-center justify-center min-h-[200px] bg-black/5 dark:bg-white/5">
            {activeTab === "original" && originalUrl && <img src={originalUrl} alt="Original" className="max-h-[400px] max-w-full object-contain rounded" />}
            {activeTab === "segmented" && segmentedUrl && <img src={segmentedUrl} alt="Segmented" className="max-h-[400px] max-w-full object-contain rounded" />}
            {activeTab === "remix" && remixUrl && <img src={remixUrl} alt="Remix" className="max-h-[400px] max-w-full object-contain rounded" />}
          </div>
        </div>
      )}

      {/* ═══ Audio Player + Transcript (Audio media type) ═══ */}
      {isAudio && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            <FileText size={16} className="text-accent-blue" />
            Audio Analysis
          </h3>
          {/* Audio player if S3 URL available */}
          {result.s3_upload_key && (
            <div className="mb-4">
              <audio controls className="w-full rounded" src={result.s3_upload_key}>
                Your browser does not support the audio element.
              </audio>
            </div>
          )}
          {/* Transcript extracted by Gemini */}
          {result._transcript && (
            <div className="p-3 bg-surface-inset/50 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-semibold uppercase text-text-muted tracking-wider">Transcript</span>
                {result._transcript.language && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent-blue/10 text-accent-blue font-semibold uppercase">
                    {result._transcript.language}
                  </span>
                )}
              </div>
              <p className="text-[13px] text-text-muted leading-relaxed whitespace-pre-wrap">
                {result._transcript.transcript}
              </p>
            </div>
          )}
        </div>
      )}

      {/* ═══ Video Violations Timeline ═══ */}
      {isVideo && violationsTimeline.length > 0 && violationsTimeline.some((v) => typeof v === "object" && v !== null && ("start_seconds" in v || "start" in v)) && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Violations Timeline ({violationsTimeline.length})</h3>
          <div className="space-y-2">
            {violationsTimeline.map((v, i) => {
              const item = v as Record<string, unknown>;
              const start = (item.start_seconds ?? item.start) as number | undefined;
              const end = (item.end_seconds ?? item.end) as number | undefined;
              const type = (item.type as string) ?? "visual";
              const severity = (item.severity as string) ?? "warning";
              const desc = (item.description as string) ?? (item.region_description as string) ?? "";
              const clipUrl = item.clip_url as string | undefined;
              const violationIndex = (item.violation_index ?? i) as number;

              return (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-surface-inset/50 border-l-4 border-amber-500">
                  <div className="shrink-0 text-center">
                    <span className="block text-[10px] text-text-muted font-mono">#{violationIndex}</span>
                    {start != null && end != null && (
                      <span className="block text-code-xs font-mono text-accent-blue bg-accent-blue/10 px-1.5 py-0.5 rounded mt-0.5">
                        {formatSeconds(start)}–{formatSeconds(end)}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[10px] font-semibold uppercase text-text-muted bg-surface-inset px-1.5 py-0.5 rounded">{type}</span>
                      <span className="text-[10px] font-semibold uppercase text-amber-600 dark:text-amber-400">{severity}</span>
                    </div>
                    <p className="text-[13px] text-text-muted">{desc}</p>
                  </div>
                  {clipUrl && (
                    <a
                      href={clipUrl.startsWith("http") ? clipUrl : `${API_BASE}${clipUrl}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 flex items-center gap-1 text-xs text-accent-blue hover:underline"
                    >
                      <ExternalLink size={12} />
                      Clip
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ═══ High Risk Indicators ═══ */}
      {highRiskIndicators && highRiskIndicators.length > 0 && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-3">High Risk Indicators ({highRiskIndicators.length})</h3>
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

      {/* ═══ Verification (Bookmark-style URL cards) ═══ */}
      {verification && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-500" />
              Verification
            </h3>
            <div className="flex items-center gap-3 text-xs text-text-muted">
              <span>Confidence: <strong className="text-text-primary">{verification.confidence}</strong></span>
              <span>Confirmed: <strong className="text-emerald-500">{verification.confirmed_ratio}</strong></span>
            </div>
          </div>

          {verification.verified && verification.verified.length > 0 && (
            <div className="space-y-3">
              {verification.verified.map((v, i) => (
                <div key={i} className="rounded-lg border bg-surface-inset/30 p-3">
                  <div className="flex items-start gap-2 mb-2">
                    <span className={`mt-0.5 text-sm ${v.confirmed ? "text-emerald-500" : "text-red-500"}`}>
                      {v.confirmed ? "✓" : "✗"}
                    </span>
                    <span className="text-[13px] font-medium text-text-primary">{v.violation}</span>
                  </div>
                  {/* Bookmark-style source cards */}
                  {v.sources && v.sources.length > 0 && (
                    <div className="ml-5 space-y-1.5">
                      {v.sources.map((src, j) => (
                        <a
                          key={j}
                          href={src}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2.5 rounded-md border bg-background px-3 py-2 hover:border-accent-blue hover:bg-accent-blue/5 transition-colors group"
                        >
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-surface-inset group-hover:bg-accent-blue/10">
                            <Globe size={14} className="text-text-muted group-hover:text-accent-blue" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-text-primary truncate group-hover:text-accent-blue">{getDomain(src)}</p>
                            <p className="text-[10px] text-text-muted truncate">{src}</p>
                          </div>
                          <ExternalLink size={12} className="shrink-0 text-text-muted group-hover:text-accent-blue" />
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ Suggestion ═══ */}
      {suggestion && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Suggestion</h3>
          <p className="text-[13px] text-text-muted leading-relaxed">{suggestion}</p>
        </div>
      )}

      {/* ═══ Localization Plan ═══ */}
      {localizationPlan && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Localization Plan</h3>
          <p className="text-[13px] text-text-muted leading-relaxed">{localizationPlan}</p>
        </div>
      )}

      {/* ═══ No Issues ═══ */}
      {!hasViolations && (
        <div className="result-card bg-surface-card rounded-xl p-8 shadow-[0_0_0_1px_rgba(0,0,0,0.08)] flex flex-col items-center justify-center text-center gap-3">
          <div className="h-12 w-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
            <svg className="h-6 w-6 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="font-semibold text-text-primary">All checks passed</p>
          <p className="text-code-xs text-text-muted">This asset meets all compliance requirements.</p>
        </div>
      )}

      {/* ═══ Auto-Remix Button ═══ */}
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
