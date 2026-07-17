import { useRef, useState, useEffect, useCallback } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  TrendingUp,
  Calendar,
  ExternalLink,
  Zap,
  Sparkles,
  Globe,
  Users,
  PlayCircle,
  Image,
  AlignLeft,
  Layers,
  AlertCircle,
  MapPin,
} from "lucide-react";
import {
  fetchTrends,
  fetchCulturalEvents,
} from "@/services/trendsApi";
import type { TrendItem, CulturalEvent } from "@/services/trendsApi";

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function formatDate(d: string): string {
  return new Date(d).toLocaleDateString("en-MY", { day: "numeric", month: "short" });
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
  const views = item.engagement_metrics?.views ?? 0;
  const likes = item.engagement_metrics?.likes ?? 0;
  const velocity = views > 0 ? Math.min(Math.round((likes / views) * 100 * 10), 99) : 0;

  return (
    <div className="trend-card bg-surface-elevated border border-border-default rounded-xl overflow-hidden group hover:border-accent-blue/40 transition-all duration-200 cursor-pointer shadow-xs retina-border">
      <div className="relative h-40 bg-surface-inset overflow-hidden flex items-center justify-center">
        <div className="text-text-caption opacity-30">
          {contentTypeIcon(item.content_type)}
        </div>
        {item.cultural_event_tag && (
          <div className="absolute top-2 left-2 bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">
            {item.cultural_event_tag.replace(/_/g, " ").toUpperCase()}
          </div>
        )}
        <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] font-bold px-1.5 py-0.5 rounded backdrop-blur-sm">
          {formatCount(views)}
        </div>
      </div>

      <div className="p-4">
        <h4 className="font-bold text-[13px] text-text-heading mb-1 line-clamp-2">
          {item.title || "Trending Content"}
        </h4>
        {item.hashtags.length > 0 && (
          <p className="text-[11px] text-text-caption mb-3 truncate">
            {item.hashtags.slice(0, 3).map((h) => `#${h}`).join(" ")}
          </p>
        )}
        <div className="flex justify-between items-center mb-4">
          <div className="text-center">
            <span className="block text-[9px] uppercase font-bold text-text-caption/60">Views</span>
            <span className="font-mono text-sm font-bold text-text-heading">{formatCount(views)}</span>
          </div>
          <div className="text-center">
            <span className="block text-[9px] uppercase font-bold text-text-caption/60">Velocity</span>
            <span className="font-mono text-sm font-bold text-accent-blue">+{velocity}%</span>
          </div>
        </div>
        <div className="flex gap-2">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 py-1.5 text-center rounded-lg border border-border-default text-[12px] font-semibold text-text-body hover:bg-surface-inset transition-colors flex items-center justify-center gap-1"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink size={11} /> View
          </a>
          <button className="flex-1 py-1.5 rounded-lg bg-text-primary dark:bg-white text-white dark:text-text-primary text-[12px] font-semibold hover:opacity-90 transition-all active:scale-95">
            Campaign
          </button>
        </div>
      </div>
    </div>
  );
}

interface EventCardProps {
  event: CulturalEvent;
}

function EventCard({ event }: EventCardProps) {
  const daysUntil = Math.ceil(
    (new Date(event.start_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  );
  const typeColor = EVENT_TYPE_COLORS[event.event_type] ?? "bg-gray-100 text-gray-700";

  return (
    <div className="event-card p-4 rounded-lg bg-surface-inset border-l-4 border-accent-blue hover:bg-surface-elevated transition-colors cursor-pointer retina-border">
      <span className="text-[11px] font-bold text-accent-blue uppercase block mb-1">
        {formatDate(event.start_date)} — {formatDate(event.end_date)}
      </span>
      <h4 className="font-bold text-[14px] text-text-heading mb-2">{event.name}</h4>
      <div className="flex flex-wrap gap-1 mb-3">
        <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${typeColor}`}>
          {event.event_type}
        </span>
        {event.tags.slice(0, 2).map((tag) => (
          <span key={tag} className="text-[10px] bg-surface-panel border border-border-subtle px-2 py-0.5 rounded">
            {tag}
          </span>
        ))}
      </div>
      <div className="flex justify-between items-center border-t border-border-subtle pt-2">
        <span className="text-[10px] uppercase text-text-caption font-bold">
          {daysUntil > 0 ? `in ${daysUntil}d` : daysUntil === 0 ? "today" : "ongoing"}
        </span>
        <span className="font-mono text-[14px] font-bold text-accent-blue">{event.impact_score}/100</span>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function DashboardTrends() {
  const containerRef = useRef<HTMLDivElement>(null);

  const [platform, setPlatform] = useState("");
  const [eventMarket, setEventMarket] = useState(detectUserMarket);
  const [trendsData, setTrendsData] = useState<Record<string, TrendItem[]>>({});
  const [lastRefresh, setLastRefresh] = useState<Record<string, string>>({});
  const [events, setEvents] = useState<CulturalEvent[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null);

  const allItems = Object.values(trendsData).flat();
  const filteredItems = platform ? (trendsData[platform] ?? []) : allItems;

  const synergyEvent = events.find((ev) =>
    allItems.some((item) => item.cultural_event_tag === ev.name.toLowerCase().replace(/\s+/g, "_"))
  );
  const synergyItems = synergyEvent
    ? allItems.filter((i) => i.cultural_event_tag === synergyEvent.name.toLowerCase().replace(/\s+/g, "_"))
    : [];

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [trendsRes, eventsRes] = await Promise.all([
        fetchTrends(platform || undefined, eventMarket === "all" ? undefined : eventMarket),
        fetchCulturalEvents(eventMarket === "all" ? undefined : eventMarket, 60),
      ]);
      setTrendsData(trendsRes.trends || {});
      setLastRefresh(trendsRes.last_refresh || {});
      setTotalItems(trendsRes.total_items || 0);
      setEmptyMessage(trendsRes.message ?? null);
      setEvents(eventsRes.events || []);
    } catch {
      setError("Failed to load trends. Data may be outdated or unavailable.");
    } finally {
      setIsLoading(false);
    }
  }, [platform, eventMarket]);

  useEffect(() => { loadData(); }, [loadData]);

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
    <div ref={containerRef} className="min-h-screen bg-background p-8 font-hanken">
      <div className="max-w-[1200px] mx-auto space-y-8">

        {/* ── Hero Header ────────────────────────────────────────────────── */}
        <section className="hero-section">
          <div className="flex items-center gap-2 mb-3">
            <span className="bg-text-primary text-white dark:bg-white dark:text-text-primary px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase">
              Live Feed
            </span>
            <span className="text-text-caption text-[12px]">
              {Object.keys(lastRefresh).length > 0
                ? `Last updated ${formatDate(Object.values(lastRefresh)[0])}`
                : "Not yet scraped"}
            </span>
          </div>

          <h2 className="text-xl font-bold tracking-tight text-text-heading mb-2">
            {synergyEvent
              ? `Trend Synergy: ${synergyEvent.name} × Social Content`
              : "Trend Intelligence Dashboard"}
          </h2>

          {synergyEvent ? (
            <p className="text-label-ui text-text-caption max-w-2xl mb-5">
              Our engine detected {synergyItems.length} trending content piece
              {synergyItems.length !== 1 ? "s" : ""} overlapping with{" "}
              <strong className="text-text-heading">{synergyEvent.name}</strong>.
              Ads blending this theme show higher engagement in the Malaysian market.
            </p>
          ) : (
            <p className="text-label-ui text-text-caption max-w-2xl mb-5">
              {totalItems > 0
                ? `${totalItems} trending pieces scraped across TikTok, Instagram, YouTube and Facebook Ads.`
                : "Trend scraping runs weekly. Trigger a manual refresh to load data."}
            </p>
          )}

          <div className="flex gap-3">
            <a
              href="/dashboard/generate"
              className="bg-text-primary text-white dark:bg-white dark:text-text-primary px-5 py-2 rounded-lg font-semibold text-[14px] hover:opacity-90 transition-all flex items-center gap-2 active:scale-95"
            >
              <Zap size={16} /> Explore Spikes
            </a>
          </div>
        </section>

        {/* ── Error Banner ────────────────────────────────────────────────── */}
        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-[13px] font-medium">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* ── Event Calendar (full width) ─────────────────────────────────── */}
        <div className="bg-surface-elevated border border-border-default rounded-xl p-6 retina-border shadow-xs">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-6">
            <div>
              <h3 className="font-bold text-base text-text-heading flex items-center gap-2">
                <Calendar size={18} className="text-accent-blue" />
                Contextual Event Calendar
              </h3>
              <p className="text-[12px] text-text-caption mt-1 flex items-center gap-1">
                <MapPin size={11} />
                Next 60 days • {MARKET_OPTIONS.find(m => m.value === eventMarket)?.flag}{" "}
                {MARKET_OPTIONS.find(m => m.value === eventMarket)?.label ?? eventMarket}
                {eventMarket !== "all" && " + Global"}
              </p>
            </div>
            <select
              value={eventMarket}
              onChange={(e) => setEventMarket(e.target.value)}
              className="bg-surface-inset border border-border-default rounded-lg text-[13px] py-1.5 px-3 text-text-body cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-blue/20"
            >
              {MARKET_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.flag} {m.label}
                </option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <div className="grid grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-36 rounded-lg bg-surface-inset animate-pulse" />
              ))}
            </div>
          ) : events.length === 0 ? (
            <p className="text-text-caption text-[13px] py-4">No upcoming events found.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {events.slice(0, 6).map((ev) => (
                <EventCard key={ev.id} event={ev} />
              ))}
            </div>
          )}
        </div>

        {/* ── Synergy Insight ─────────────────────────────────────────────── */}
        {synergyEvent && synergyItems.length > 0 && (
          <div className="synergy-card relative bg-surface-elevated border-2 border-accent-blue/20 rounded-xl p-6 overflow-hidden retina-border shadow-xs">
            <div className="absolute top-0 left-0 w-1 h-full bg-accent-blue" />
            <div className="flex items-start gap-6 pl-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles size={16} className="text-accent-blue" />
                  <h4 className="font-bold text-sm text-accent-blue">
                    Detected Synergy: "{synergyEvent.name} × Content"
                  </h4>
                </div>
                <p className="text-label-ui text-text-caption mb-5">
                  {synergyItems.length} trending piece{synergyItems.length !== 1 ? "s" : ""} overlap
                  with this cultural event. High probability of engagement for ads blending these themes.
                </p>
                <div className="flex gap-3">
                  <a
                    href="/dashboard/generate"
                    className="bg-text-primary text-white dark:bg-white dark:text-text-primary px-4 py-2 rounded-lg text-[13px] font-semibold hover:opacity-90 transition-all flex items-center gap-2 active:scale-95"
                  >
                    Generate Idea <span aria-hidden>→</span>
                  </a>
                  <button className="text-text-caption hover:text-text-heading text-[13px] font-semibold flex items-center gap-1 transition-colors">
                    Save Insight
                  </button>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono text-[28px] font-extrabold text-accent-blue">
                  +{synergyItems.length * 8}%
                </div>
                <div className="text-[10px] uppercase font-bold text-text-caption">Velocity</div>
              </div>
            </div>
          </div>
        )}

        {/* ── Industry Intel ───────────────────────────────────────────────── */}
        <section>
          <div className="flex justify-between items-center mb-5">
            <h3 className="font-bold text-base text-text-heading flex items-center gap-2">
              <TrendingUp size={18} className="text-accent-blue" />
              Industry Intel
              {totalItems > 0 && (
                <span className="text-[13px] font-normal text-text-caption ml-1">
                  ({totalItems} items)
                </span>
              )}
            </h3>
            <div className="flex gap-2">
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="bg-surface-inset border border-border-default rounded-lg text-[13px] py-1.5 px-3 text-text-body cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-blue/20"
              >
                {PLATFORMS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
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
              {filteredItems.slice(0, 16).map((item) => (
                <TrendCard key={item.id} item={item} />
              ))}
            </div>
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
        </section>
      </div>
    </div>
  );
}
