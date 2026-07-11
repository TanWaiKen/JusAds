import { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  CheckCircle,
  Edit3,
  Globe,
  Image,
  Mic,
  PlayCircle,
  AlignLeft,
  Sparkles,
  Calendar,
  ExternalLink,
  Loader2,
} from "lucide-react";

gsap.registerPlugin(useGSAP);

// ─── Types ───────────────────────────────────────────────────────────────────

export interface TrendReference {
  title: string;
  url: string;
  platform: string;
  relevance: string;
}

export interface EventRef {
  name: string;
  dates: string;
  tags: string[];
}

export interface CreativePlan {
  target_platforms: string[];
  media_types: string[];
  trend_references: TrendReference[];
  creative_direction: string;
  target_language: string;
  cultural_event_refs: EventRef[];
}

interface CreativePlanApprovalProps {
  plan: CreativePlan | null;
  isLoading: boolean;
  onApprove: () => void;
  onRequestChanges: (feedback: string) => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const MEDIA_ICONS: Record<string, React.ReactNode> = {
  text: <AlignLeft size={14} />,
  image: <Image size={14} />,
  video: <PlayCircle size={14} />,
  audio: <Mic size={14} />,
};

const LANGUAGE_LABELS: Record<string, string> = {
  ms: "Bahasa Melayu",
  zh: "Mandarin Chinese",
  ta: "Tamil",
  en: "English",
};

// ─── Component ───────────────────────────────────────────────────────────────

export function CreativePlanApproval({
  plan,
  isLoading,
  onApprove,
  onRequestChanges,
}: CreativePlanApprovalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ── Entrance animation
  useGSAP(() => {
    if (!plan || isLoading) return;
    const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
    tl.from(".plan-header", { y: 16, autoAlpha: 0, duration: 0.4 })
      .from(".plan-section", { y: 12, autoAlpha: 0, stagger: 0.08, duration: 0.35 }, "-=0.2")
      .from(".plan-actions", { y: 10, autoAlpha: 0, duration: 0.3 }, "-=0.2");
  }, { scope: containerRef, dependencies: [plan, isLoading] });

  const handleSubmitFeedback = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    await onRequestChanges(feedback.trim());
    setFeedback("");
    setShowFeedback(false);
    setIsSubmitting(false);
  };

  // ── Loading state
  if (isLoading) {
    return (
      <div className="bg-surface-elevated border border-border-default rounded-xl p-6 retina-border shadow-xs">
        <div className="flex items-center gap-3">
          <Loader2 size={18} className="text-accent-blue animate-spin" />
          <span className="text-[14px] font-semibold text-text-heading">
            Director Agent is planning your creative strategy…
          </span>
        </div>
        <div className="mt-4 space-y-2">
          <div className="h-3 bg-surface-inset rounded w-3/4 animate-pulse" />
          <div className="h-3 bg-surface-inset rounded w-1/2 animate-pulse" />
        </div>
      </div>
    );
  }

  if (!plan) return null;

  return (
    <div ref={containerRef} className="bg-surface-elevated border-2 border-accent-blue/20 rounded-xl p-6 retina-border shadow-xs relative overflow-hidden">
      {/* Accent bar */}
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accent-blue to-purple-500" />

      {/* Header */}
      <div className="plan-header flex items-start justify-between mb-5">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-accent-blue" />
          <h3 className="font-bold text-[18px] text-text-heading">Creative Plan</h3>
          <span className="text-[11px] bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 px-2 py-0.5 rounded font-bold">
            Awaiting Approval
          </span>
        </div>
        <span className="text-[12px] text-text-caption">
          Language: {LANGUAGE_LABELS[plan.target_language] ?? plan.target_language}
        </span>
      </div>

      {/* Creative Direction */}
      <div className="plan-section mb-5">
        <p className="text-[14px] text-text-body leading-relaxed bg-surface-inset border border-border-subtle p-4 rounded-lg">
          {plan.creative_direction}
        </p>
      </div>

      {/* Platforms + Media Types */}
      <div className="plan-section flex flex-wrap gap-4 mb-5">
        <div>
          <span className="text-[10px] font-bold uppercase text-text-caption/60 block mb-1.5">Platforms</span>
          <div className="flex gap-1.5">
            {plan.target_platforms.map((p) => (
              <span key={p} className="px-2.5 py-1 rounded-full bg-surface-inset border border-border-subtle text-[12px] font-semibold text-text-body flex items-center gap-1">
                <Globe size={11} /> {p}
              </span>
            ))}
          </div>
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase text-text-caption/60 block mb-1.5">Media Types</span>
          <div className="flex gap-1.5">
            {plan.media_types.map((m) => (
              <span key={m} className="px-2.5 py-1 rounded-full bg-accent-blue/10 border border-accent-blue/20 text-[12px] font-semibold text-accent-blue flex items-center gap-1">
                {MEDIA_ICONS[m] ?? null} {m}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Trend References */}
      {plan.trend_references.length > 0 && (
        <div className="plan-section mb-5">
          <span className="text-[10px] font-bold uppercase text-text-caption/60 block mb-2">Trend Inspirations</span>
          <div className="space-y-2">
            {plan.trend_references.map((ref, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-surface-inset rounded-lg border border-border-subtle">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.5 bg-surface-panel border border-border-default rounded font-bold text-text-caption">
                      {ref.platform}
                    </span>
                    <span className="text-[13px] font-semibold text-text-heading truncate">{ref.title}</span>
                  </div>
                  <p className="text-[12px] text-text-caption mt-1">{ref.relevance}</p>
                </div>
                <a href={ref.url} target="_blank" rel="noopener noreferrer" className="text-accent-blue hover:opacity-70 shrink-0">
                  <ExternalLink size={14} />
                </a>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cultural Events */}
      {plan.cultural_event_refs.length > 0 && (
        <div className="plan-section mb-5">
          <span className="text-[10px] font-bold uppercase text-text-caption/60 block mb-2">Cultural Context</span>
          <div className="flex flex-wrap gap-2">
            {plan.cultural_event_refs.map((ev, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                <Calendar size={12} className="text-amber-600" />
                <span className="text-[12px] font-semibold text-amber-800 dark:text-amber-300">{ev.name}</span>
                <span className="text-[10px] text-amber-600 dark:text-amber-400">{ev.dates}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="plan-actions flex gap-3 pt-4 border-t border-border-subtle">
        <button
          onClick={onApprove}
          className="flex-1 py-2.5 rounded-lg bg-green-600 text-white font-semibold text-[14px] hover:bg-green-700 transition-all active:scale-95 flex items-center justify-center gap-2"
        >
          <CheckCircle size={16} /> Approve & Generate
        </button>
        <button
          onClick={() => setShowFeedback(!showFeedback)}
          className="flex-1 py-2.5 rounded-lg border border-border-default text-text-body font-semibold text-[14px] hover:bg-surface-inset transition-all active:scale-95 flex items-center justify-center gap-2"
        >
          <Edit3 size={16} /> Request Changes
        </button>
      </div>

      {/* Feedback textarea */}
      {showFeedback && (
        <div className="mt-4 space-y-3">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Describe what you'd like changed (e.g., 'Add video format', 'Focus on Gen Z audience')…"
            className="w-full p-3 rounded-lg border border-border-default bg-surface-inset text-[13px] text-text-body placeholder:text-text-caption/60 resize-none focus:outline-none focus:ring-2 focus:ring-accent-blue/20"
            rows={3}
          />
          <button
            onClick={handleSubmitFeedback}
            disabled={!feedback.trim() || isSubmitting}
            className="px-4 py-2 rounded-lg bg-text-primary dark:bg-white text-white dark:text-text-primary text-[13px] font-semibold hover:opacity-90 transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : null}
            Submit Feedback
          </button>
        </div>
      )}
    </div>
  );
}
