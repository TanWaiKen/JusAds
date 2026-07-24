import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { ArrowLeft, AudioLines, CheckCircle2, Loader2, Rocket, Send, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { VideoPlanStoryboard } from "@/components/workspace/canvas/VideoPlanStoryboard";
import {
  distributeToAccounts,
  executeVideoPlan,
  getDistributionAccounts,
  getGeneratedAds,
  normalizeVideoPlan,
  publishAd,
  streamChat,
  streamGuidedGeneration,
  type DistributionAccount,
  type GeneratedAdView,
  type VideoPlan,
} from "@/services/generationApi";
import { getTask } from "@/services/taskApi";

interface GuidedNavigationState {
  guidedMode?: boolean;
  designType?: string;
  guidedInputs?: Record<string, string>;
  guidedReferences?: string[];
}

const MEDIA_FILTERS = ["all", "image", "video", "audio", "text"] as const;
type MediaFilter = typeof MEDIA_FILTERS[number];

export default function EasyResultsPage() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const guidedState = location.state as GuidedNavigationState | null;
  const started = useRef(false);
  const [ads, setAds] = useState<GeneratedAdView[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [videoPlan, setVideoPlan] = useState<VideoPlan | null>(null);
  const [planRendering, setPlanRendering] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>("all");
  const [accounts, setAccounts] = useState<DistributionAccount[]>([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [publishBusy, setPublishBusy] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishedCaption, setPublishedCaption] = useState("");
  const [distributionBusy, setDistributionBusy] = useState(false);
  const [distributionError, setDistributionError] = useState<string | null>(null);
  const [distributed, setDistributed] = useState(false);

  const refreshOutputs = useCallback(async () => {
    if (!projectId || !taskId) return;
    const generated = await getGeneratedAds(projectId, taskId);
    setAds(generated);
    setSelectedId((current) => current && generated.some((ad) => ad.adId === current)
      ? current
      : generated[0]?.adId ?? null);
  }, [projectId, taskId]);

  const refreshVideoPlan = useCallback(async () => {
    if (!projectId || !taskId) return null;
    const task = await getTask(projectId, taskId);
    const rawPlan = task.type === "generation"
      ? task.pipeline_state?.video_plan
      : undefined;
    const normalized = normalizeVideoPlan(rawPlan);
    setVideoPlan(normalized ?? null);
    return normalized ?? null;
  }, [projectId, taskId]);

  useEffect(() => {
    if (!projectId || !taskId) return;

    let active = true;
    void Promise.all([
      getGeneratedAds(projectId, taskId).catch(() => []),
      getTask(projectId, taskId).catch(() => null),
    ]).then(([generated, task]) => {
      if (!active) return;
      setAds(generated);
      setSelectedId(generated[0]?.adId ?? null);
      const rawPlan = task?.type === "generation"
        ? task.pipeline_state?.video_plan
        : undefined;
      setVideoPlan(normalizeVideoPlan(rawPlan) ?? null);
    }).finally(() => {
      if (active) setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [projectId, taskId]);

  useEffect(() => {
    if (
      started.current ||
      loading ||
      !guidedState?.guidedMode ||
      !guidedState.designType ||
      !guidedState.guidedInputs ||
      !projectId ||
      !taskId
    ) return;

    started.current = true;
    navigate(location.pathname, { replace: true, state: null });
    if (videoPlan) return;

    void Promise.resolve().then(async () => {
      setGenerating(true);
      try {
        for await (const event of streamGuidedGeneration(
          projectId,
          taskId,
          guidedState.designType!,
          guidedState.guidedInputs!,
          guidedState.guidedReferences ?? [],
        )) {
          if (event.error) throw new Error(event.error);
          const eventPlan = normalizeVideoPlan(
            event.video_plan
              ?? (event.pipeline_state as Record<string, unknown> | undefined)?.video_plan,
          );
          if (eventPlan) setVideoPlan(eventPlan);
        }
        const persistedPlan = await refreshVideoPlan();
        await refreshOutputs();
        toast.success(persistedPlan ? "Storyboard ready for review." : "Your ad is ready.");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Could not generate the ad");
      } finally {
        setGenerating(false);
      }
    });
  }, [
    guidedState,
    loading,
    location.pathname,
    navigate,
    projectId,
    refreshOutputs,
    refreshVideoPlan,
    taskId,
    videoPlan,
  ]);

  useEffect(() => {
    void getDistributionAccounts().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  const filteredAds = mediaFilter === "all"
    ? ads
    : ads.filter((ad) => ad.mediaType === mediaFilter);
  const selected = filteredAds.find((ad) => ad.adId === selectedId) ?? filteredAds[0] ?? null;
  const isPublished = selected?.generationStatus === "published" || publishBusy === false && publishedCaption !== "";
  const selectedAccounts = accounts.filter((account) => selectedAccountIds.includes(account.id));
  const selectedIsVerticalImage = selected?.mediaType === "image" && (() => {
    const [width, height] = (selected.aspectRatio ?? "").split(":").map(Number);
    return Boolean(width && height && width / height < 0.75);
  })();

  useEffect(() => {
    if (!selected) return;
    const recommendedPlatforms = selected.mediaType === "video"
      ? ["tiktok", "instagram"]
      : selected.mediaType === "image"
        ? ["instagram", "tiktok"]
        : ["instagram", "tiktok"];
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setSelectedAccountIds(accounts
        .filter((account) => recommendedPlatforms.includes(account.platform.toLowerCase()))
        .map((account) => account.id));
      setPublishedCaption(selected.caption ?? "");
      setPublishError(null);
      setDistributionError(null);
      setDistributed(false);
    });
    return () => {
      active = false;
    };
  }, [selected, accounts]);

  const submitFeedback = async () => {
    if (!feedback.trim() || !projectId || !taskId || !selected) return;
    setGenerating(true);
    try {
      const instruction = `Revise the selected Version for this feedback: ${feedback.trim()}`;
      for await (const event of streamChat(
        projectId,
        taskId,
        instruction,
        selected.publicUrl ? [selected.publicUrl] : [],
        undefined,
        undefined,
        undefined,
        undefined,
        { parentAdId: selected.adId, parentAssetUrl: selected.publicUrl ?? undefined },
      )) {
        if (event.error) throw new Error(event.error);
      }
      setFeedback("");
      await refreshOutputs();
      toast.success("New variation generated.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not generate a variation");
    } finally {
      setGenerating(false);
    }
  };

  const handleContinuePlan = async (approvedPlan: VideoPlan) => {
    if (!projectId || !taskId) return;
    setPlanRendering(true);
    try {
      for await (const event of executeVideoPlan(projectId, taskId, approvedPlan)) {
        if (event.error) throw new Error(event.error);
      }
      await Promise.all([refreshOutputs(), refreshVideoPlan()]);
      toast.success("Video render completed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not render the approved video");
    } finally {
      setPlanRendering(false);
    }
  };

  const handlePublish = async () => {
    if (!projectId || !taskId || !selected) return;
    setPublishBusy(true);
    setPublishError(null);
    try {
      const result = await publishAd(projectId, taskId, selected.adId);
      setPublishedCaption(result.caption);
      await refreshOutputs();
      toast.success("Ad approved. A platform-ready caption is prepared.");
    } catch (error) {
      setPublishError(error instanceof Error ? error.message : "Could not publish this ad");
    } finally {
      setPublishBusy(false);
    }
  };

  const handleDistribute = async () => {
    if (!projectId || !taskId || !selected || selectedAccounts.length === 0) return;
    setDistributionBusy(true);
    setDistributionError(null);
    try {
      const result = await distributeToAccounts(projectId, taskId, selected.adId, selectedAccounts);
      if (result.caption) setPublishedCaption(result.caption);
      const failures = result.results.filter((item) => item.status === "failed");
      if (failures.length > 0) {
        setDistributionError(`${failures.length} account${failures.length === 1 ? "" : "s"} could not be reached. You can retry them.`);
      } else {
        setDistributed(true);
        toast.success(`Distributed to ${selectedAccounts.length} account${selectedAccounts.length === 1 ? "" : "s"}.`);
      }
    } catch (error) {
      setDistributionError(error instanceof Error ? error.message : "Could not distribute this ad");
    } finally {
      setDistributionBusy(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-full w-full max-w-6xl flex-col gap-6 p-6">
      <header className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px_minmax(0,1fr)]">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => navigate(`/dashboard/project/${projectId}/easy/${taskId}`)}
            className="mb-3 flex items-center gap-1.5 text-xs font-medium text-text-muted hover:text-text-heading"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Generate new ad
          </button>
          <h1 className="text-2xl font-semibold tracking-tight text-text-heading">
            {videoPlan ? "Review your video storyboard" : "Your generated ads"}
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            {videoPlan
              ? "Review the scenes, confirm the approved facts and localization, then start production."
              : "Choose a version, preview it, then describe what you would like to improve."}
          </p>
        </div>
        <div className="flex w-full max-w-[360px] justify-self-center rounded-lg border border-border-default bg-surface-card p-1 shadow-sm xl:max-w-none xl:justify-self-stretch">
          <button
            type="button"
            onClick={() => navigate(`/dashboard/project/${projectId}/easy/${taskId}`)}
            className="flex-1 rounded-md px-6 py-1.5 text-xs font-semibold bg-primary text-primary-foreground shadow-sm"
          >
            Easy Mode
          </button>
          <button
            type="button"
            onClick={() => navigate(`/dashboard/project/${projectId}/advance/${taskId}`)}
            className="flex-1 rounded-md px-6 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
          >
            Advanced Mode
          </button>
        </div>
        <div aria-hidden="true" />
      </header>

      {loading || generating && ads.length === 0 && !videoPlan ? (
        <div className="flex min-h-80 flex-col items-center justify-center gap-3 rounded-2xl border border-border-default bg-surface-card">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
          <p className="text-sm text-text-muted">{generating ? "Generating your ad…" : "Loading generated ads…"}</p>
        </div>
      ) : videoPlan ? (
        <section className="rounded-2xl border border-border-default bg-surface-card p-4 sm:p-6">
          <VideoPlanStoryboard
            key={videoPlan.planId}
            plan={videoPlan}
            onContinue={(plan) => void handleContinuePlan(plan)}
            isRendering={planRendering}
          />
        </section>
      ) : ads.length === 0 ? (
        <div className="flex min-h-80 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border-default bg-surface-card text-center">
          <Sparkles className="h-7 w-7 text-primary" />
          <p className="font-medium text-text-heading">No generated ads yet</p>
          <p className="max-w-sm text-sm text-text-muted">Return to Easy Mode and submit a short brief to create your first version.</p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="space-y-4">
            <div className="flex flex-wrap gap-2" aria-label="Filter generated ads by media type">
              {MEDIA_FILTERS.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setMediaFilter(filter)}
                  aria-pressed={mediaFilter === filter}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                    mediaFilter === filter
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border-default bg-surface-card text-text-muted hover:border-primary/50 hover:text-text-heading"
                  }`}
                >
                  {filter === "all" ? `All (${ads.length})` : `${filter} (${ads.filter((ad) => ad.mediaType === filter).length})`}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {filteredAds.map((ad, index) => {
                const active = ad.adId === selected?.adId;
                return (
                  <button
                    key={ad.adId}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setSelectedId(ad.adId)}
                    className={`overflow-hidden rounded-xl border text-left transition-all ${
                      active ? "border-primary ring-2 ring-primary/20" : "border-border-default hover:border-primary/50"
                    }`}
                  >
                    {ad.mediaType === "image" && ad.publicUrl ? (
                      <img
                        src={ad.publicUrl}
                        alt={`Generated version ${index + 1}`}
                        className="aspect-square w-full bg-surface-muted object-contain"
                      />
                    ) : ad.mediaType === "video" && ad.publicUrl ? (
                      <video
                        src={ad.publicUrl}
                        className="aspect-square w-full bg-black object-cover"
                        muted
                        playsInline
                        preload="metadata"
                      />
                    ) : ad.mediaType === "audio" ? (
                      <div className="flex aspect-square flex-col items-center justify-center gap-3 bg-gradient-to-br from-primary/15 via-surface-card to-accent-blue/10 text-primary">
                        <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/20 bg-surface-card shadow-sm">
                          <AudioLines className="h-7 w-7" aria-hidden="true" />
                        </span>
                        <span className="text-xs font-semibold text-text-heading">Audio file</span>
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                          MP3
                        </span>
                      </div>
                    ) : (
                      <div className="flex aspect-square items-center justify-center bg-surface-inset text-xs text-text-muted">{ad.mediaType}</div>
                    )}
                    <div className="px-3 py-2 text-xs font-medium text-text-heading">Version {index + 1}</div>
                  </button>
                );
              })}
            </div>

            {filteredAds.length === 0 && (
              <p className="rounded-xl border border-dashed border-border-default p-6 text-center text-sm text-text-muted">
                No {mediaFilter} output exists for this task yet.
              </p>
            )}

            {selected?.mediaType === "image" && selected.publicUrl && (
              <div className="overflow-hidden rounded-2xl border border-border-default bg-surface-card">
                <img src={selected.publicUrl} alt="Selected generated ad" className="max-h-[560px] w-full object-contain bg-surface-inset" />
              </div>
            )}

            {selected?.mediaType === "video" && selected.publicUrl && (
              <div className="overflow-hidden rounded-2xl border border-border-default bg-black">
                <video
                  src={selected.publicUrl}
                  controls
                  playsInline
                  preload="metadata"
                  className="max-h-[560px] w-full object-contain"
                >
                  Your browser does not support video playback.
                </video>
              </div>
            )}

            {selected?.mediaType === "audio" && selected.publicUrl && (
              <div className="rounded-2xl border border-border-default bg-surface-card p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                  Audio preview
                </p>
                <audio
                  src={selected.publicUrl}
                  controls
                  preload="metadata"
                  className="mt-3 w-full"
                >
                  Your browser does not support audio playback.
                </audio>
                {selected.caption && (
                  <div className="mt-4 rounded-xl bg-surface-inset p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                      Transcript
                    </p>
                    <p className="mt-2 text-sm leading-6 text-text-body">{selected.caption}</p>
                  </div>
                )}
              </div>
            )}
          </section>

          <aside className="h-fit rounded-2xl border border-border-default bg-surface-card p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Selected version</p>
            <p className="mt-2 text-sm font-medium text-text-heading">{selected?.platform || "Generated ad"} · {selected?.mediaType}</p>
            <div className="my-5 border-t border-border-default" />
            <label htmlFor="easy-feedback" className="text-sm font-medium text-text-heading">Refine this ad</label>
            <Textarea
              id="easy-feedback"
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              placeholder="e.g. Make the background warmer and use less text."
              className="mt-2 min-h-28 resize-none"
              disabled={generating}
            />
            <Button className="mt-3 w-full" disabled={!feedback.trim() || generating} onClick={submitFeedback}>
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Generate another version
            </Button>

            {selected && selected.complianceStatus !== "non-compliant" && (
              <section className="mt-5 border-t border-border-default pt-5">
                <p className="text-sm font-medium text-text-heading">Publish & distribute</p>
                <p className="mt-1 text-xs text-text-muted">We generate platform-safe copy when you approve this version.</p>

                {!isPublished ? (
                  <Button className="mt-3 w-full" onClick={handlePublish} disabled={publishBusy}>
                    {publishBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                    {publishBusy ? "Preparing caption…" : "Approve & prepare caption"}
                  </Button>
                ) : (
                  <>
                    <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
                      <div className="flex items-center gap-1.5 font-medium"><CheckCircle2 className="h-3.5 w-3.5" /> Approved</div>
                      {publishedCaption && <p className="mt-2 text-emerald-900">{publishedCaption}</p>}
                    </div>

                    <div className="mt-4 space-y-2">
                      <p className="text-xs font-medium text-text-heading">Recommended accounts</p>
                      {selectedIsVerticalImage && selectedAccounts.some((account) => account.platform.toLowerCase() === "instagram") && (
                        <p className="text-xs text-text-muted">This vertical image will publish to Instagram as a Story to preserve its full composition.</p>
                      )}
                      {accounts.length === 0 ? (
                        <p className="rounded-lg border border-dashed border-border-default p-3 text-xs text-text-muted">Connect a social account first to distribute this ad.</p>
                      ) : accounts.map((account) => {
                        const active = selectedAccountIds.includes(account.id);
                        return (
                          <label key={account.id} className="flex cursor-pointer items-center justify-between rounded-lg border border-border-default px-3 py-2 text-xs hover:border-primary/50">
                            <span><span className="font-medium capitalize text-text-heading">{account.platform}</span><span className="ml-1 text-text-muted">{account.label}</span></span>
                            <input
                              type="checkbox"
                              checked={active}
                              onChange={() => setSelectedAccountIds((current) => active ? current.filter((id) => id !== account.id) : [...current, account.id])}
                            />
                          </label>
                        );
                      })}
                    </div>

                    <Button className="mt-3 w-full" disabled={distributionBusy || selectedAccounts.length === 0} onClick={handleDistribute}>
                      {distributionBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : distributed ? <CheckCircle2 className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                      {distributionBusy ? "Distributing…" : distributed ? "Distributed" : `Distribute to ${selectedAccounts.length || "selected"} account${selectedAccounts.length === 1 ? "" : "s"}`}
                    </Button>
                  </>
                )}
                {publishError && <p className="mt-2 text-xs text-red-600">{publishError}</p>}
                {distributionError && <p className="mt-2 text-xs text-red-600">{distributionError}</p>}
              </section>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
