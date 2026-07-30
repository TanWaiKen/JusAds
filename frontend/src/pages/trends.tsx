import { useRef, useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  TrendingUp,
  Calendar,
  ExternalLink,
  Sparkles,
  Globe,
  Users,
  PlayCircle,
  Image,
  AlignLeft,
  Layers,
  AlertCircle,
  MapPin,
  RefreshCw,
  ArrowRight,
  Clock3,
  Target,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  findCreativeIdeas,
  loadTrendsDashboard,
  refreshTrendResearch,
} from "@/services/trendsService";
import type { CreativeTrendSignal, TrendItem, CulturalEvent, DailyCreativeIdea } from "@/models/trends";
import type { TrendBrief } from "@/lib/sessionStorage";
import { useAuth } from "@/hooks/useAuth";

gsap.registerPlugin(useGSAP);

// ─── Platform config ──────────────────────────────────────────────────────────

const PLATFORMS = [
  { value: "", label: "All Platforms" },
  { value: "tiktok", label: "TikTok", color: "text-pink-500" },
  { value: "instagram", label: "Instagram", color: "text-purple-500" },
  { value: "youtube", label: "YouTube", color: "text-red-500" },
  { value: "facebook_ads", label: "Facebook Ads", color: "text-blue-600" },
];

// ─── Market / Country config ──────────────────────────────────────────────────

const MARKET_OPTIONS: { value: string; label: string; flag: string }[] = [
  { value: "malaysia", label: "Malaysia", flag: "🇲🇾" },
  { value: "thailand", label: "Thailand", flag: "🇹🇭" },
  { value: "singapore", label: "Singapore", flag: "🇸🇬" },
  { value: "indonesia", label: "Indonesia", flag: "🇮🇩" },
  { value: "vietnam", label: "Vietnam", flag: "🇻🇳" },
  { value: "philippines", label: "Philippines", flag: "🇵🇭" },
  { value: "all", label: "All Markets", flag: "🌏" },
];

/** Map browser locale/timezone to a default market. */
function detectUserMarket(): string {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone.toLowerCase();
  if (tz.includes("kuala_lumpur") || tz.includes("singapore")) return "malaysia";
  if (tz.includes("bangkok")) return "thailand";
  if (tz.includes("jakarta")) return "indonesia";
  if (tz.includes("ho_chi_minh") || tz.includes("hanoi")) return "vietnam";
  if (tz.includes("manila")) return "philippines";
  const lang = navigator.language.toLowerCase();
  if (lang.startsWith("ms") || lang === "en-my") return "malaysia";
  if (lang.startsWith("th")) return "thailand";
  if (lang.startsWith("id")) return "indonesia";
  if (lang.startsWith("vi")) return "vietnam";
  if (lang.startsWith("fil") || lang === "en-ph") return "philippines";
  return "malaysia";
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  religious: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  festive: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  sports: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  national: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  global: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
};

const EVENTS_PER_PAGE = 4;
const SOURCES_PER_PAGE = 8;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function formatDate(d: string): string {
  return new Date(d).toLocaleDateString("en-MY", { day: "numeric", month: "short" });
}

function formatDateTime(d?: string): string | null {
  if (!d) return null;
  const date = new Date(d);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("en-MY", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function getPlanObjective(plan: DailyCreativeIdea): string {
  const text = `${plan.title} ${plan.idea} ${plan.hook}`.toLowerCase();
  if (/buy|shop|order|sale|discount|promo|register|sign up|book now/.test(text)) {
    return "Conversion / action";
  }
  return "Awareness & engagement";
}

function getYouTubeThumbnail(url: string): string | null {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
    const pathParts = parsed.pathname.split("/").filter(Boolean);
    let videoId: string | null = null;

    if (host === "youtu.be") {
      videoId = pathParts[0] ?? null;
    } else if (["youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"].includes(host)) {
      if (parsed.pathname === "/watch") {
        videoId = parsed.searchParams.get("v");
      } else if (["shorts", "embed", "live"].includes(pathParts[0] ?? "")) {
        videoId = pathParts[1] ?? null;
      }
    }

    return videoId && videoId !== "placeholder" && /^[A-Za-z0-9_-]{11}$/.test(videoId)
      ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
      : null;
  } catch {
    return null;
  }
}

function contentTypeIcon(type: string) {
  switch (type) {
    case "video": return <PlayCircle size={12} />;
    case "image": return <Image size={12} />;
    case "ad": return <Layers size={12} />;
    default: return <AlignLeft size={12} />;
  }
}

// ─── Components ───────────────────────────────────────────────────────────────

interface TrendCardProps {
  item: TrendItem;
}

function TrendCard({ item }: TrendCardProps) {
  const views = item.engagement_metrics?.views;
  const previewUrl = getYouTubeThumbnail(item.url);
  const [failedPreviewUrl, setFailedPreviewUrl] = useState<string | null>(null);
  const showPreview = Boolean(previewUrl) && failedPreviewUrl !== previewUrl;

  return (
    <article className="trend-card self-start bg-surface-elevated border border-border-default rounded-xl overflow-hidden group hover:border-accent-blue/40 transition-all duration-200 shadow-xs retina-border">
      {showPreview && previewUrl && (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="relative block h-40 bg-surface-inset overflow-hidden"
          aria-label={`Watch ${item.title || "trending video"} on YouTube`}
        >
          <img
            src={previewUrl}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setFailedPreviewUrl(previewUrl)}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
          <span className="absolute inset-0 flex items-center justify-center bg-black/10">
            <PlayCircle size={38} className="text-white drop-shadow-lg" aria-hidden="true" />
          </span>
          {item.cultural_event_tag && (
            <span className="absolute top-2 left-2 bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">
              {item.cultural_event_tag.replace(/_/g, " ").toUpperCase()}
            </span>
          )}
          {typeof views === "number" && views > 0 && (
            <span className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] font-bold px-1.5 py-0.5 rounded backdrop-blur-sm">
              {formatCount(views)} views
            </span>
          )}
        </a>
      )}

      <div className="p-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <span className="text-[10px] font-bold uppercase tracking-wide text-accent-blue">
            {item.platform.replace(/_/g, " ")}
          </span>
          <span className="flex items-center gap-1 text-[10px] capitalize text-text-caption">
            {contentTypeIcon(item.content_type)} {item.content_type}
          </span>
        </div>
        <h4 className="font-bold text-[13px] text-text-heading mb-1 line-clamp-2">
          {item.title || "Trending Content"}
        </h4>
        {item.hashtags.length > 0 && (
          <p className="text-[11px] text-text-caption mb-3 truncate">
            {item.hashtags.slice(0, 3).map((h) => `#${h}`).join(" ")}
          </p>
        )}
        {item.cultural_event_tag && !showPreview && (
          <span className="inline-flex mb-3 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 text-[10px] font-bold px-2 py-0.5 rounded">
            {item.cultural_event_tag.replace(/_/g, " ")}
          </span>
        )}
        {typeof views === "number" && views > 0 && (
        <div className="mb-4">
          <span className="block text-[9px] uppercase font-bold text-text-caption/60">Views</span>
          <span className="font-mono text-sm font-bold text-text-heading">
            {formatCount(views)}
          </span>
        </div>
        )}
        <div className="flex gap-2">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full py-1.5 text-center rounded-lg border border-border-default text-[12px] font-semibold text-text-body hover:bg-surface-inset transition-colors flex items-center justify-center gap-1"
          >
            <ExternalLink size={11} /> {showPreview ? "Watch source" : "View source"}
          </a>
        </div>
      </div>
    </article>
  );
}

interface CreativeSignalCardProps {
  signal: CreativeTrendSignal;
  onUseInCampaign: (signal: CreativeTrendSignal) => void;
}

function CreativeSignalCard({ signal, onUseInCampaign }: CreativeSignalCardProps) {
  return (
    <article className="signal-card self-start rounded-xl border border-border-default bg-surface-elevated p-5 shadow-xs retina-border">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-[10px] font-bold uppercase tracking-wide text-accent-blue">
          {signal.signal_type.replace(/_/g, " ")}
        </span>
        <span className="text-[10px] capitalize text-text-caption">{signal.momentum} · {signal.confidence} confidence</span>
      </div>
      <h4 className="mb-2 text-sm font-bold text-text-heading">{signal.title}</h4>
      <p className="mb-3 rounded-lg bg-surface-inset p-3 text-xs leading-relaxed text-text-body">
        <strong className="text-text-heading">Try this: </strong>{signal.suggested_adaptation}
      </p>
      <details className="mb-3 rounded-lg border border-border-default">
        <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-text-body">Why this idea</summary>
        <div className="space-y-2 border-t border-border-default px-3 py-2 text-xs leading-relaxed text-text-caption">
          <p>{signal.summary}</p>
          {signal.do_not_do && <p><strong className="text-text-heading">Avoid: </strong>{signal.do_not_do}</p>}
        </div>
      </details>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onUseInCampaign(signal)}
          className="flex-1 rounded-lg bg-text-primary py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 dark:bg-white dark:text-text-primary"
        >
          Use in campaign
        </button>
        {signal.evidence_urls[0] && (
          <a
            href={signal.evidence_urls[0]}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-border-default px-3 py-1.5 text-xs font-semibold text-text-body hover:bg-surface-inset"
          >
            Evidence
          </a>
        )}
      </div>
    </article>
  );
}

interface EventCardProps {
  event: CulturalEvent;
  todayTimestamp: number;
}

function EventCard({ event, todayTimestamp }: EventCardProps) {
  const daysUntil = Math.ceil(
    (new Date(event.start_date).getTime() - todayTimestamp) / (1000 * 60 * 60 * 24)
  );
  const typeColor = EVENT_TYPE_COLORS[event.event_type] ?? "bg-gray-100 text-gray-700";
  const sourceUrl = event.source_payload?.source_url;
  const isOfficialCalendar = event.source === "official_calendar_2026";

  return (
    <article className="event-card rounded-xl border border-border-default bg-surface-card p-4 shadow-xs">
      <span className="text-[11px] font-bold text-accent-blue uppercase block mb-1">
        {formatDate(event.start_date)} — {formatDate(event.end_date)}
      </span>
      <h4 className="font-bold text-[14px] text-text-heading mb-2">{event.name}</h4>
      <div className="mb-3">
        <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${typeColor}`}>
          {event.event_type}
        </span>
      </div>
      <div className="flex justify-between items-center border-t border-border-subtle pt-2">
        <span className="text-[10px] uppercase text-text-caption font-bold">
          {daysUntil > 0 ? `in ${daysUntil}d` : daysUntil === 0 ? "today" : "ongoing"}
        </span>
        <span className="text-[11px] font-semibold text-text-body">Relevance {event.impact_score}</span>
      </div>
      {isOfficialCalendar && (
        <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-text-caption">
          <span>Verified official calendar</span>
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-accent-blue hover:underline"
            >
              Source
            </a>
          )}
        </div>
      )}
    </article>
  );
}

interface PaginationProps {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  label: string;
}

function Pagination({ page, pageSize, totalItems, onPageChange, label }: PaginationProps) {
  const totalPages = Math.ceil(totalItems / pageSize);
  if (totalPages <= 1) return null;
  const start = page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, totalItems);

  return (
    <div className="mt-4 flex items-center justify-between text-[11px] text-text-caption">
      <span>{start}–{end} of {totalItems}</span>
      <div className="flex gap-1">
        <button type="button" onClick={() => onPageChange(page - 1)} disabled={page === 0} aria-label={`Previous ${label} page`} className="rounded-md border border-border-default p-1 disabled:opacity-40">
          <ChevronLeft size={14} aria-hidden="true" />
        </button>
        <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages - 1} aria-label={`Next ${label} page`} className="rounded-md border border-border-default p-1 disabled:opacity-40">
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function DashboardTrends() {
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { user } = useAuth();
  const ownerEmail = user?.profile?.email ?? "";
  const [platform, setPlatform] = useState("");
  const [eventMarket, setEventMarket] = useState(detectUserMarket);
  const [trendsData, setTrendsData] = useState<Record<string, TrendItem[]>>({});
  const [lastRefresh, setLastRefresh] = useState<Record<string, string>>({});
  const [researchProvider, setResearchProvider] = useState("none");
  const [freshness, setFreshness] = useState("unavailable");
  const [researchSources, setResearchSources] = useState<Array<{ url: string; title?: string }>>([]);
  const [events, setEvents] = useState<CulturalEvent[]>([]);
  const [eventSourceCounts, setEventSourceCounts] = useState<Record<string, number>>({});
  const [latestPredictHqSync, setLatestPredictHqSync] = useState<string | null>(null);
  const [totalItems, setTotalItems] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null);

  const [isResearching, setIsResearching] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [creativeSignals, setCreativeSignals] = useState<CreativeTrendSignal[]>([]);
  const [signalMessage, setSignalMessage] = useState<string | null>(null);
  const [isSignalResearching, setIsSignalResearching] = useState(false);
  const [dailyIdea, setDailyIdea] = useState<DailyCreativeIdea | null>(null);
  const [dailyIdeaError, setDailyIdeaError] = useState<string | null>(null);
  const [youtubeHookReferenceCount, setYoutubeHookReferenceCount] = useState(0);
  const [youtubeHooksCached, setYoutubeHooksCached] = useState<boolean | null>(null);
  const [eventPage, setEventPage] = useState(0);
  const [sourcePage, setSourcePage] = useState(0);
  const [todayTimestamp] = useState(() => Date.now());

  const allItems = Object.values(trendsData).flat();
  const filteredItems = platform ? (trendsData[platform] ?? []) : allItems;
  // A small verified calendar layer must not be buried behind a noisy event
  // feed. Show it first, then preserve chronological order within each group.
  const displayedEvents = useMemo(() => [...events].sort((a, b) => {
    const sourcePriority = Number(b.source === "official_calendar_2026") - Number(a.source === "official_calendar_2026");
    return sourcePriority || a.start_date.localeCompare(b.start_date);
  }), [events]);
  const pagedEvents = displayedEvents.slice(eventPage * EVENTS_PER_PAGE, (eventPage + 1) * EVENTS_PER_PAGE);
  const pagedItems = filteredItems.slice(sourcePage * SOURCES_PER_PAGE, (sourcePage + 1) * SOURCES_PER_PAGE);

  const handleResearch = useCallback(async () => {
    setIsResearching(true);
    setError(null);
    try {
      const summary = await refreshTrendResearch({ ownerEmail, market: eventMarket });
      if (summary.status === "partial") setError(summary.message);
      await loadData();
    } catch {
      setError("Research request failed. Please try again.");
    } finally {
      setIsResearching(false);
    }
  // `loadData` is declared below this callback. Referencing it in the hook
  // dependency expression triggers a temporal-dead-zone error during render;
  // it is safely resolved only when the user invokes this handler.
  }, [ownerEmail, eventMarket]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await loadTrendsDashboard({ ownerEmail, market: eventMarket, platform });
      setTrendsData(data.trendsData);
      setDailyIdea(data.dailyIdea);
      setDailyIdeaError(data.dailyIdea ? null : "No campaign recommendation yet.");
      setYoutubeHookReferenceCount(data.youtubeHookReferenceCount);
      setYoutubeHooksCached(data.youtubeHooksCached);
      setLastRefresh(data.lastRefresh);
      setResearchProvider("cache");
      setFreshness(Object.keys(data.trendsData).length > 0 ? "cached" : "unavailable");
      setResearchSources([]);
      setTotalItems(data.totalItems);
      setEmptyMessage(data.emptyMessage);
      setEvents(data.events);
      setEventSourceCounts(data.eventSourceCounts);
      setLatestPredictHqSync(data.latestPredictHqSync);
      setCreativeSignals(data.creativeSignals);
      setSignalMessage(data.signalMessage);
      setEventPage(0);
      setSourcePage(0);
    } catch {
      setError("Failed to load saved trend research. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, [ownerEmail, platform, eventMarket]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setError(null);
    try {
      const summary = await refreshTrendResearch({ ownerEmail, market: eventMarket });
      if (summary.status === "partial") {
        setError(summary.message);
      }
      // After refresh completes, reload the page data to show new results
      await loadData();
    } catch {
      setError("Refresh request failed. Please try again.");
    } finally {
      setIsRefreshing(false);
    }
  }, [ownerEmail, eventMarket, loadData]);

  const handleResearchCreativeSignals = useCallback(async () => {
    setIsSignalResearching(true);
    setError(null);
    try {
      const response = await findCreativeIdeas({ ownerEmail, market: eventMarket, platform });
      setCreativeSignals(response.signals || []);
      setSignalMessage(response.message ?? null);
    } catch {
      setError("Creative signal research could not verify any evidence-backed ideas right now.");
    } finally {
      setIsSignalResearching(false);
    }
  }, [ownerEmail, eventMarket, platform]);

  const handleUseSignalInCampaign = useCallback((signal: CreativeTrendSignal) => {
    const trendBrief: TrendBrief = {
      signalId: signal.id,
      title: signal.title,
      signalType: signal.signal_type,
      suggestedAdaptation: signal.suggested_adaptation,
      doNotDo: signal.do_not_do,
      evidenceUrls: signal.evidence_urls,
    };
    navigate("/dashboard/new", { state: { trendBrief } });
  }, [navigate]);

  const handleUseDailyPlan = useCallback(() => {
    if (!dailyIdea) return;
    navigate("/dashboard/new", { state: { trendBrief: {
      signalId: `daily-plan:${dailyIdea.market}:${dailyIdea.idea_date}`,
      title: dailyIdea.title,
      signalType: "seasonal_or_cultural_moment",
      suggestedAdaptation: `${dailyIdea.idea} Opening hook: ${dailyIdea.hook} Recommended format: ${dailyIdea.format}`,
      doNotDo: "Do not invent unsupported product claims, discounts, or event affiliations.",
      evidenceUrls: dailyIdea.source_urls,
    } } });
  }, [dailyIdea, navigate]);

  useEffect(() => {
    const requestId = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(requestId);
  }, [loadData]);

  useGSAP(() => {
    if (isLoading) return;
    const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
    tl.fromTo(".hero-section", { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.5 });
    if (containerRef.current?.querySelectorAll(".event-card").length) {
      tl.fromTo(".event-card", { y: 16, autoAlpha: 0 }, { y: 0, autoAlpha: 1, stagger: 0.07, duration: 0.4 }, "-=0.3");
    }
    if (containerRef.current?.querySelectorAll(".synergy-card").length) {
      tl.fromTo(".synergy-card", { y: 12, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.4 }, "-=0.2");
    }
    if (containerRef.current?.querySelectorAll(".trend-card").length) {
      tl.fromTo(".trend-card", { y: 20, autoAlpha: 0 }, { y: 0, autoAlpha: 1, stagger: 0.05, duration: 0.4 }, "-=0.3");
    }
  }, { scope: containerRef, dependencies: [isLoading, filteredItems.length, events.length] });

  return (
    <div ref={containerRef} className="min-h-screen bg-gradient-to-b from-surface-inset/30 via-background to-background p-6 font-hanken">
      <div className="max-w-[1200px] mx-auto space-y-6">

        {/* ── Hero Header ────────────────────────────────────────────────── */}
        <section className="hero-section">
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-text-primary text-white dark:bg-white dark:text-text-primary px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase">
              {freshness === "fresh" ? "Updated" : "Saved"}
            </span>
            <span className="text-text-caption text-[12px]">
              {freshness === "fresh"
                ? `${totalItems} ideas found with ${researchProvider.replace("_", " ")}`
                : freshness === "cached"
                  ? `${totalItems} saved ideas`
                  : "No saved ideas"}
            </span>
            {researchSources.length > 0 && (
              <span className="text-text-caption text-[11px]">{researchSources.length} sources</span>
            )}
          </div>

          <h1 className="mb-1 text-[24px] font-semibold tracking-tight text-text-heading">Content ideas</h1>

          <p className="max-w-2xl text-sm text-text-caption">
            {totalItems > 0
              ? "Browse research and review the original source before using it."
              : "Browse research for your next ad."}
          </p>
        </section>

        {/* ── Error Banner ────────────────────────────────────────────────── */}
        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-[13px] font-medium">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* ── Event Calendar (full width) ─────────────────────────────────── */}
        <section className="bg-surface-elevated border border-border-default rounded-2xl p-5 retina-border shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-start gap-4 mb-5">
            <div>
              <h3 className="font-bold text-base text-text-heading flex items-center gap-2">
                <Calendar size={18} className="text-accent-blue" />
                Upcoming moments
              </h3>
              <p className="text-[12px] text-text-caption mt-1 flex items-center gap-1">
                <MapPin size={11} />
                Next 60 days in {MARKET_OPTIONS.find(m => m.value === eventMarket)?.label ?? eventMarket}
              </p>
              <p className="mt-1 text-[11px] text-text-caption">
                {latestPredictHqSync
                  ? `PredictHQ last refreshed ${formatDate(latestPredictHqSync)} · ${eventSourceCounts.predicthq ?? 0} imported events in this view.`
                  : "No PredictHQ import has completed yet; this view currently uses curated calendar data only."}
              </p>
            </div>
            <div className="ml-auto flex shrink-0 items-center gap-2">
              <select
                value={eventMarket}
                onChange={(e) => {
                  setEventMarket(e.target.value);
                  setEventPage(0);
                  setSourcePage(0);
                }}
                className="bg-surface-inset border border-border-default rounded-lg text-[13px] py-1.5 px-3 text-text-body cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-blue/20"
              >
                {MARKET_OPTIONS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
              <button
              type="button"
              onClick={handleResearch}
              disabled={isResearching || isLoading}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-border-default bg-surface-elevated px-3 py-1.5 text-xs font-semibold text-text-heading transition-colors hover:bg-surface-inset disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Sparkles size={14} className={isResearching ? "animate-spin" : ""} />
              {isResearching ? "Refreshing…" : "Refresh research"}
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-36 rounded-lg bg-surface-inset animate-pulse" />
              ))}
            </div>
          ) : events.length === 0 ? (
            <p className="text-text-caption text-[13px] py-4">
              No events are stored for this market in the selected window. {latestPredictHqSync ? "PredictHQ has run; expand the date range or choose another market." : "Run the PredictHQ importer before treating this as an empty market."}
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {pagedEvents.map((ev) => (
                <EventCard key={ev.id} event={ev} todayTimestamp={todayTimestamp} />
              ))}
            </div>
          )}
          <Pagination page={eventPage} pageSize={EVENTS_PER_PAGE} totalItems={displayedEvents.length} onPageChange={setEventPage} label="moments" />
        </section>

        {/* ── Creative Trend Signals ─────────────────────────────────────── */}
        <section>
          <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <h3 className="flex items-center gap-2 text-base font-bold text-text-heading">
                <Sparkles size={18} className="text-accent-blue" />
                Ad ideas
              </h3>
              <p className="mt-1 text-xs text-text-caption">
                Current hooks and formats with sources you can review.
              </p>
            </div>
            <button
              type="button"
              onClick={handleResearchCreativeSignals}
              disabled={isSignalResearching || isLoading}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-text-primary px-4 py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-text-primary"
            >
              <Sparkles size={14} className={isSignalResearching ? "animate-spin" : ""} />
              {isSignalResearching ? "Generating ideas..." : "Generate campaign ideas"}
            </button>
          </div>
          {creativeSignals.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border-default bg-surface-elevated p-5 text-sm text-text-caption">
              {signalMessage ?? "No saved ad ideas yet. Generate campaign ideas to get started."}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {creativeSignals.map((signal) => (
                <CreativeSignalCard key={signal.id} signal={signal} onUseInCampaign={handleUseSignalInCampaign} />
              ))}
            </div>
          )}
        </section>

        <section className="overflow-hidden rounded-2xl border border-border-default bg-surface-elevated shadow-xs retina-border">
          <div className="border-b border-border-default bg-gradient-to-r from-amber-50 via-surface-elevated to-surface-elevated px-5 py-5 dark:from-amber-950/20">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                    <Sparkles size={17} aria-hidden="true" />
                  </span>
                  <h3 className="text-base font-bold text-text-heading">Campaign planner</h3>
                  <p className="mt-1 text-xs text-text-caption">Uses only upcoming events with relevance 70/100 or higher. Relevance is the normalized event rank from PredictHQ or the manual event source—not an AI confidence score.</p>
                </div>
              </div>
            </div>
          </div>

          {!dailyIdea ? (
            <div className="p-5">
              <div className="rounded-xl border border-dashed border-border-default bg-surface-inset p-5 text-sm text-text-caption">
                <p className="font-semibold text-text-body">No campaign recommendation is ready yet</p>
                <p className="mt-1">{dailyIdeaError ?? "Loading…"}</p>
              </div>
            </div>
          ) : (
            <div className="p-5">
              <div className="mb-5 flex flex-wrap items-center gap-2 text-[11px]">
                <span className="rounded-full bg-amber-100 px-2.5 py-1 font-semibold text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                  {dailyIdea.market}
                </span>
                <span className="rounded-full bg-surface-inset px-2.5 py-1 font-medium capitalize text-text-caption">
                  {dailyIdea.confidence} confidence
                </span>
                {dailyIdea.event_name && (
                  <span className="rounded-full bg-surface-inset px-2.5 py-1 font-medium text-text-caption">
                    Timed to: {dailyIdea.event_name}
                  </span>
                )}
                {formatDateTime(dailyIdea.generated_at) && (
                  <span className="ml-auto inline-flex items-center gap-1 text-text-caption">
                    <Clock3 size={12} aria-hidden="true" />
                    Generated {formatDateTime(dailyIdea.generated_at)}
                  </span>
                )}
              </div>

              <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
                <div>
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-300">Recommended campaign</p>
                  <h4 className="text-xl font-bold tracking-tight text-text-heading">{dailyIdea.title}</h4>
                  <p className="mt-3 text-sm leading-6 text-text-body">{dailyIdea.idea}</p>
                  {dailyIdea.why_today && (
                    <div className="mt-4 rounded-xl border border-border-default bg-surface-inset px-4 py-3 text-xs leading-5 text-text-caption">
                      <strong className="text-text-heading">Why now: </strong>{dailyIdea.why_today}
                    </div>
                  )}

                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-border-default p-3">
                      <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-text-caption"><Target size={12} aria-hidden="true" /> Recommended objective</span>
                      <p className="mt-1.5 text-sm font-semibold text-text-heading">{getPlanObjective(dailyIdea)}</p>
                    </div>
                    <div className="rounded-xl border border-border-default p-3">
                      <span className="text-[10px] font-bold uppercase tracking-wide text-text-caption">Recommended format</span>
                      <p className="mt-1.5 text-sm font-semibold text-text-heading">{dailyIdea.format}</p>
                    </div>
                    <div className="rounded-xl border border-border-default p-3">
                      <span className="text-[10px] font-bold uppercase tracking-wide text-text-caption">Opening hook</span>
                      <p className="mt-1.5 text-sm font-semibold leading-5 text-text-heading">{dailyIdea.hook}</p>
                    </div>
                  </div>
                </div>

                <aside className="rounded-xl border border-border-default bg-surface-inset p-4">
                  <h5 className="text-sm font-bold text-text-heading">Execution checklist</h5>
                  {dailyIdea.execution_steps.length > 0 ? (
                    <ol className="mt-3 space-y-3">
                      {dailyIdea.execution_steps.slice(0, 4).map((step, index) => (
                        <li key={`${index}-${step}`} className="flex gap-2.5 text-xs leading-5 text-text-body">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">{index + 1}</span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-3 text-xs leading-5 text-text-caption">Use the objective, format and opening hook to turn this recommendation into your campaign brief.</p>
                  )}
                  <div className="mt-5 border-t border-border-default pt-4">
                    <button type="button" onClick={handleUseDailyPlan} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-text-primary px-4 py-2.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 dark:bg-white dark:text-text-primary">
                      Use in campaign <ArrowRight size={14} aria-hidden="true" />
                    </button>
                  </div>
                </aside>
              </div>

              <div className="mt-5 border-t border-border-default pt-4 text-[11px] text-text-caption">
                {dailyIdea.source_urls.length > 0 && `${dailyIdea.source_urls.length} source link${dailyIdea.source_urls.length === 1 ? "" : "s"}`}
              </div>
            </div>
          )}
        </section>

        {/* ── Industry Intel ───────────────────────────────────────────────── */}
        <section>
          <div className="flex justify-between items-center mb-5">
            <h3 className="font-bold text-base text-text-heading flex items-center gap-2">
              <TrendingUp size={18} className="text-accent-blue" />
              Sources
              {totalItems > 0 && (
                <span className="text-[13px] font-normal text-text-caption ml-1">
                  ({totalItems} items)
                </span>
              )}
            </h3>
            <div className="flex items-center gap-2">
              {youtubeHookReferenceCount > 0 && (
                <span
                  title={youtubeHooksCached ? "Saved YouTube/Reels hook references" : "Fresh YouTube/Reels hook references"}
                  className="rounded-full bg-surface-inset px-2 py-1 text-[10px] font-semibold text-text-caption"
                >
                  YouTube/Reels refs · {youtubeHookReferenceCount}
                </span>
              )}
              <select
                value={platform}
                onChange={(e) => {
                  setPlatform(e.target.value);
                  setSourcePage(0);
                }}
                className="bg-surface-inset border border-border-default rounded-lg text-[13px] py-1.5 px-3 text-text-body cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-blue/20"
              >
                {PLATFORMS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
              <button
                onClick={handleRefresh}
                disabled={isRefreshing || isLoading}
                className="border border-border-default bg-surface-elevated text-text-body px-3 py-1.5 rounded-lg font-semibold text-[13px] hover:bg-surface-inset transition-all flex items-center gap-2 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh Sources"
              >
                <RefreshCw size={14} className={isRefreshing ? "animate-spin" : ""} />
                {isRefreshing ? "Refreshing..." : "Refresh sources"}
              </button>
            </div>
          </div>

          {isLoading && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="rounded-xl bg-surface-elevated border border-border-default overflow-hidden animate-pulse">
                  <div className="h-40 bg-surface-inset" />
                  <div className="p-4 space-y-2">
                    <div className="h-3 bg-surface-inset rounded w-3/4" />
                    <div className="h-2 bg-surface-inset rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!isLoading && filteredItems.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Globe size={40} className="text-text-caption/30 mb-3" />
              <h4 className="font-bold text-[16px] text-text-heading mb-1">No trend data yet</h4>
              <p className="text-text-caption text-[13px] mb-4">
                {emptyMessage ?? "Trend data refreshes weekly. Check back later for the latest insights."}
              </p>
            </div>
          )}

          {!isLoading && filteredItems.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
              {pagedItems.map((item) => (
                <TrendCard key={item.id} item={item} />
              ))}
            </div>
          )}
          {!isLoading && filteredItems.length > 0 && (
            <Pagination page={sourcePage} pageSize={SOURCES_PER_PAGE} totalItems={filteredItems.length} onPageChange={setSourcePage} label="sources" />
          )}

          {Object.keys(lastRefresh).length > 0 && (
            <div className="mt-4 flex flex-wrap gap-3">
              {Object.entries(lastRefresh).map(([p, ts]) => (
                <span key={p} className="text-[11px] text-text-caption flex items-center gap-1">
                  <Users size={10} />
                  {p}: {formatDate(ts)}
                </span>
              ))}
            </div>
          )}

          {/* Research Sources — clickable reference links from Google grounding */}
          {researchSources.length > 0 && (
            <div className="mt-6 bg-surface-elevated border border-border-default rounded-xl p-5 retina-border shadow-xs">
              <h4 className="font-bold text-[13px] text-text-heading mb-3 flex items-center gap-2">
                <Globe size={14} className="text-accent-blue" />
                Research Sources ({researchSources.length})
              </h4>
              <ul className="space-y-2">
                {researchSources.slice(0, 5).map((src, idx) => (
                  <li key={idx}>
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[12px] text-accent-blue hover:underline flex items-center gap-1.5 truncate"
                    >
                      <ExternalLink size={11} className="shrink-0" />
                      {src.title || src.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
