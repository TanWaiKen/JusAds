import { useRef, useState, type ReactNode } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import type { ComplianceResult } from "@/services/complianceApi";
import { normalizeViolations } from "@/services/complianceApi";
import { Button } from "@/components/ui/button";
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

/** Render the limited Markdown emitted by the compliance-research agents. */
function renderResearchInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index} className="font-semibold text-text-primary">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index} className="rounded bg-surface-inset px-1 py-0.5 font-mono text-[0.9em]">{part.slice(1, -1)}</code>;
    }
    return <span key={index}>{part}</span>;
  });
}

function isResearchHeading(line: string): boolean {
  return /^#{1,3}\s/.test(line) || (/^[A-Z][A-Za-z/& ]+$/.test(line) && line.length < 72);
}

function normaliseResearchText(text: string): string {
  return text
    .replaceAll("â€™", "’")
    .replaceAll("â€œ", "“")
    .replaceAll("â€", "”")
    .replaceAll("â€”", "—");
}

type ImageTab = "original" | "segmented";

export function ReviewStep({ result, onStartRemix, isRemixAvailable, mediaType }: ReviewStepProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showHighRiskConfirmation, setShowHighRiskConfirmation] = useState(false);

  // Image URLs (only relevant for image media)
  const isImage = mediaType === "image";
  const segmentedUrl = isImage ? (result.s3_segmented_key || null) : null;
  const originalUrl = isImage ? (result.s3_upload_key || null) : null;
  const hasAnyImage = isImage && !!(originalUrl || segmentedUrl);

  // Default to first available tab
  const defaultTab: ImageTab = segmentedUrl ? "segmented" : "original";
  const [activeTab, setActiveTab] = useState<ImageTab>(defaultTab);

  console.log("[ReviewStep] result:", result);

  // Derive common values
  const riskPercentage = result.risk_percentage ?? (result.score != null ? 100 - result.score : 0);
  const riskLevel = result.risk_level ?? result.risk_band ?? "Unknown";
  const explanation = result.explanation ?? "";
  const suggestion = result.suggestion;
  const highRiskIndicators = result.high_risk_indicator ?? result.high_risk_indicators;
  const localizationPlan = result.localization_plan;
  const imageReview = result.image_review;
  const requiresNewCreative = result.compliance_verdict === "rejected"
    || riskLevel === "Critical"
    || riskPercentage > 85;
  const verification = result.verification;
  const textAnnotations = result.text_annotations ?? [];
  const audioSegments = result.audio_annotations?.segments ?? result._transcript?.segments ?? [];

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

      {/* ═══ Decision summary — keep the actionable results above evidence ═══ */}
      {hasViolations && (
        <div className={`result-card rounded-xl border p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)] ${
          requiresNewCreative
            ? "border-red-500/30 bg-red-500/5"
            : "border-accent-blue/20 bg-accent-blue/5"
        }`}>
          {requiresNewCreative ? (
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-red-600 mt-0.5">block</span>
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">New creative recommended</h3>
                  <p className="mt-1 text-[13px] leading-relaxed text-text-muted">
                    This concept is not eligible for normal localization or automated remixing for the selected Malaysian audience. A new compliant concept is the safer option.
                  </p>
                </div>
              </div>
              {isRemixAvailable && (
                <Button variant="outline" size="lg" onClick={() => setShowHighRiskConfirmation(true)} className="shrink-0 gap-2 border-red-500/40 text-red-700 hover:bg-red-500/10">
                  <span className="material-symbols-outlined text-[18px]">warning</span>
                  Generate anyway
                </Button>
              )}
            </div>
          ) : isRemixAvailable ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">Ready for AI remediation</h3>
                <p className="mt-1 text-[13px] leading-relaxed text-text-muted">
                  Generate a localized compliant version while preserving the remediable parts of this asset.
                </p>
              </div>
              <Button variant="default" size="lg" onClick={onStartRemix} className="shrink-0 gap-2">
                <span className="material-symbols-outlined text-[18px]">auto_fix_high</span>
                Auto-Remix
              </Button>
            </div>
          ) : null}
        </div>
      )}

      {showHighRiskConfirmation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" aria-labelledby="high-risk-remix-title">
          <div className="w-full max-w-md rounded-xl bg-surface-card p-6 shadow-xl">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-red-600">warning</span>
              <div>
                <h3 id="high-risk-remix-title" className="text-lg font-semibold text-text-primary">Generate a high-risk remix?</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-muted">
                  This ad is rejected for the selected Malaysian audience. The generated version is only a draft and must be reviewed before use; it may still require a completely new concept.
                </p>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="outline" onClick={() => setShowHighRiskConfirmation(false)}>Cancel</Button>
              <Button variant="default" className="bg-red-600 hover:bg-red-700" onClick={() => { setShowHighRiskConfirmation(false); onStartRemix(); }}>
                Generate anyway
              </Button>
            </div>
          </div>
        </div>
      )}

      {localizationPlan && (
        <div className="result-card rounded-xl border border-accent-blue/20 bg-accent-blue/5 p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="mb-2 text-sm font-semibold text-text-primary">Localization Plan</h3>
          <p className="text-[13px] leading-relaxed text-text-muted">{localizationPlan}</p>
        </div>
      )}

      {imageReview && (
        <div className="result-card rounded-xl border border-accent-blue/20 bg-accent-blue/5 p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Image localisation &amp; evidence review</h3>
          {imageReview.copy_actions?.length > 0 && (
            <div className="mb-4 space-y-2">
              {imageReview.copy_actions.map((action, index) => (
                <div key={index} className="rounded-lg bg-surface-card p-3 text-[13px]">
                  <p className="text-text-muted">{action.original || "Promotional copy"}</p>
                  {action.replacement && <p className="mt-1 font-medium text-text-primary">{action.replacement} <span className="font-normal text-text-muted">({action.language})</span></p>}
                  {action.reason && <p className="mt-1 text-text-muted">{action.reason}</p>}
                </div>
              ))}
            </div>
          )}
          {imageReview.character_assessment && <p className="mb-3 text-[13px] leading-relaxed text-text-muted"><span className="font-medium text-text-primary">Representation: </span>{imageReview.character_assessment}</p>}
          {imageReview.claims_requiring_evidence?.length > 0 && <p className="text-[13px] leading-relaxed text-text-muted"><span className="font-medium text-text-primary">Evidence needed: </span>{imageReview.claims_requiring_evidence.join(" · ")}</p>}
          {imageReview.sensitive_content?.length > 0 && <p className="mt-2 text-[13px] leading-relaxed text-text-muted"><span className="font-medium text-text-primary">Sensitive context: </span>{imageReview.sensitive_content.join(" · ")}</p>}
        </div>
      )}

      {highRiskIndicators && highRiskIndicators.length > 0 && (
        <div className="result-card rounded-xl bg-surface-card p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Key findings ({highRiskIndicators.length})</h3>
          <ul className="space-y-2">
            {highRiskIndicators.map((indicator, i) => (
              <li key={i} className="flex items-start gap-2"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-red-500" /><span className="text-[13px] text-text-muted">{indicator}</span></li>
            ))}
          </ul>
        </div>
      )}

      {suggestion && (
        <div className="result-card rounded-xl bg-surface-card p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="mb-2 text-sm font-semibold text-text-primary">Recommended change</h3>
          <p className="text-[13px] leading-relaxed text-text-muted">{suggestion}</p>
        </div>
      )}

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
          </div>
          <div className="p-4 flex items-center justify-center min-h-[200px] bg-black/5 dark:bg-white/5">
            {activeTab === "original" && originalUrl && <img src={originalUrl} alt="Original" className="max-h-[400px] max-w-full object-contain rounded" />}
            {activeTab === "segmented" && segmentedUrl && <img src={segmentedUrl} alt="Segmented" className="max-h-[400px] max-w-full object-contain rounded" />}
          </div>
        </div>
      )}

      {/* ═══ Audio Player + Transcript (Audio media type) ═══ */}
      {mediaType === "text" && textAnnotations.length > 0 && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Flagged text</h3>
          <div className="space-y-3">
            {textAnnotations.map((annotation, index) => (
              <div key={`${annotation.start}-${index}`} className="rounded-lg bg-amber-500/5 px-3 py-2.5">
                <p className="text-[13px] leading-relaxed text-text-primary underline decoration-amber-500 decoration-2 underline-offset-4">
                  {annotation.text}
                </p>
                <p className="mt-2 text-[11px] text-text-muted">{annotation.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {isAudio && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            <FileText size={16} className="text-accent-blue" />
            Audio Analysis
          </h3>
          {/* Audio player if S3 URL available */}
          {result.s3_upload_key && (
            <div className="mb-4">
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Original audio</p>
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
              {audioSegments.length > 0 && (
                <div className="mt-3 space-y-1.5 border-t border-border-subtle pt-3">
                  {audioSegments.map((segment, index) => (
                    <div key={`${segment.start_seconds}-${index}`} className="flex gap-2 text-[12px] leading-relaxed text-text-muted">
                      <span className="shrink-0 font-mono text-accent-blue">{formatSeconds(segment.start_seconds)}–{formatSeconds(segment.end_seconds)}</span>
                      <span>{segment.text}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ═══ Original video ═══ */}
      {isVideo && result.s3_upload_key && (
        <div className="result-card overflow-hidden rounded-xl bg-surface-card shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex items-center gap-2 border-b border-outline-variant px-5 py-3"><FileText size={16} className="text-accent-blue" /><h3 className="text-sm font-semibold text-text-primary">Video evidence</h3></div>
          <video controls preload="metadata" className="max-h-[460px] w-full bg-black" src={result.s3_upload_key}>
            Your browser does not support the video element.
          </video>
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
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ═══ Research & Verification ═══ */}
      {verification && verification.research_report && (
        <div className="result-card bg-surface-card rounded-xl p-5 shadow-[0_0_0_1px_rgba(0,0,0,0.08)]">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-500" />
              Regulatory Research & Verification
            </h3>
            <div className="flex items-center gap-3 text-xs">
              <span className={`px-2.5 py-1 rounded-full font-medium ${
                verification.overall_confidence === 'high' 
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                  : verification.overall_confidence === 'medium'
                  ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                  : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400'
              }`}>
                {verification.overall_confidence || 'medium'} confidence
              </span>
              {verification.sources_count > 0 && (
                <span className="text-text-muted">
                  {verification.sources_count} {verification.sources_count === 1 ? 'source' : 'sources'}
                </span>
              )}
            </div>
          </div>

          {/* Research Report */}
          {verification.research_report !== "No regulatory research available for this content." ? (
            <div className="mb-4 p-4 rounded-lg bg-accent-blue/5 border border-accent-blue/20">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-accent-blue mb-2 flex items-center gap-2">
                <Globe size={12} />
                Research Report
              </p>
              <div className="text-[13px] text-text-primary leading-relaxed">
                {normaliseResearchText(verification.research_report).split('\n').map((line, i) => {
                  if (line.trim() === '') {
                    return <div key={i} className="h-2" />;
                  }
                  const boldHeading = line.match(/^\*\*(.+)\*\*$/);
                  if (boldHeading) {
                    return <h4 key={i} className="mt-4 mb-1.5 text-sm font-semibold text-text-primary">{boldHeading[1]}</h4>;
                  }
                  if (isResearchHeading(line)) {
                    return <h4 key={i} className="mt-4 mb-1.5 text-sm font-semibold text-text-primary">{line.replace(/^#{1,3}\s*/, '')}</h4>;
                  }
                  const bullet = line.match(/^\s*[*-]\s+(.+)$/);
                  if (bullet) {
                    return <div key={i} className="mb-1.5 flex gap-2 pl-1 text-text-muted"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-blue" /><span>{renderResearchInline(bullet[1])}</span></div>;
                  }
                  const labelledStatement = line.match(/^([^:]{2,90}):\s+(.+)$/);
                  if (labelledStatement) {
                    return <p key={i} className="mb-2 text-text-muted"><strong className="font-semibold text-text-primary">{labelledStatement[1]}:</strong>{" "}{renderResearchInline(labelledStatement[2])}</p>;
                  }
                  return <p key={i} className="mb-2 text-text-muted">{renderResearchInline(line)}</p>;
                })}
              </div>
            </div>
          ) : (
            <p className="text-xs text-text-muted italic">No regulatory research available for this content.</p>
          )}

          {/* Source References - Optional, only if sources exist */}
          {verification.sources && verification.sources.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-3">
                Source References
              </p>
              <div className="space-y-2">
                {verification.sources.map((source: any, i: number) => (
                  <a
                    key={i}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-3 rounded-md border bg-background px-3 py-2.5 hover:border-accent-blue hover:bg-accent-blue/5 transition-colors group"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded bg-surface-inset group-hover:bg-accent-blue/10 mt-0.5">
                      <Globe size={14} className="text-text-muted group-hover:text-accent-blue" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-text-primary group-hover:text-accent-blue mb-0.5">
                        {source.title || getDomain(source.url)}
                      </p>
                      {source.snippet && (
                        <p className="text-[11px] text-text-muted line-clamp-2 leading-relaxed mb-1">
                          {source.snippet}
                        </p>
                      )}
                      <p className="text-[10px] text-text-muted/70 truncate">{source.url}</p>
                    </div>
                    <ExternalLink size={12} className="shrink-0 text-text-muted group-hover:text-accent-blue mt-1" />
                  </a>
                ))}
              </div>
            </div>
          )}
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
    </div>
  );
}
