/**
 * VideoPlanStoryboard — V3 storyboard review and production approval gate.
 *
 * The review layout is designed for a resizable side panel: each scene remains
 * readable without a hidden horizontal strip, while the image preview favours
 * the visual lower area of V3 reference frames over their baked-in prompt text.
 */

import React, { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clapperboard,
  Clock,
  Grid3X3,
  Layers3,
  Loader2,
  Mic2,
  Music2,
  Play,
  ShieldCheck,
  UserRound,
  Volume2,
  WalletCards,
} from "lucide-react";
import type { VideoPlan } from "@/services/generationApi";
import { evaluateVideoPlanReadiness } from "./videoPlanReadiness";

gsap.registerPlugin(useGSAP);

interface VideoPlanStoryboardProps {
  plan: VideoPlan;
  onContinue: (plan: VideoPlan) => void;
  isRendering: boolean;
}

type CreativeMode = NonNullable<VideoPlan["creativeMode"]>;
type AudioMode = NonNullable<VideoPlan["voiceoverType"]>;

const CREATIVE_MODES: Array<{
  value: CreativeMode;
  label: string;
  description: string;
  icon: typeof UserRound;
}> = [
  {
    value: "speaker_led",
    label: "Speaker-led",
    description: "A visible person speaks. Requires script, captions, and lip-sync review.",
    icon: UserRound,
  },
  {
    value: "voiceover",
    label: "Voiceover",
    description: "Narration over visuals. Requires script and caption alignment, but no face-sync.",
    icon: Mic2,
  },
  {
    value: "music_first",
    label: "Music-first",
    description: "No spoken script. Relies on visuals, on-screen text, pacing, and music.",
    icon: Music2,
  },
];

function storyboardGridLabel(cellCount: number): string {
  if (cellCount < 2 || cellCount % 2) return `${cellCount} cells`;
  let rows = Math.floor(Math.sqrt(cellCount));
  while (rows > 1 && cellCount % rows !== 0) rows -= 1;
  return `${rows}×${cellCount / rows}`;
}

/** A single V3 storyboard shot, optimised for the Outputs review panel. */
function SceneCard({
  scene,
  onSubtitleChange,
}: {
  scene: VideoPlan["scenes"][number];
  onSubtitleChange: (index: number, value: string) => void;
}): React.ReactElement {
  const sceneNumber = scene.index + 1;

  return (
    <article className="scene-card min-w-0 overflow-hidden rounded-lg border bg-card shadow-sm">
      <div className="relative aspect-video overflow-hidden bg-muted">
        {scene.keyframeUrl ? (
          <img
            src={scene.keyframeUrl}
            alt={`Visual reference for scene ${sceneNumber}`}
            className="h-full w-full origin-bottom scale-[2.65] object-cover object-bottom"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
            <Grid3X3 size={18} />
            Scene Grid reference
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 bg-gradient-to-t from-black/75 via-black/20 to-transparent px-2.5 pb-2 pt-8 text-white">
          <span className="rounded bg-black/50 px-1.5 py-0.5 text-[10px] font-bold">Scene {sceneNumber}</span>
          {scene.shotType && (
            <span className="max-w-[65%] truncate rounded bg-primary/90 px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground" title={scene.shotType}>
              {scene.shotType}
            </span>
          )}
        </div>
      </div>

      <div className="flex min-w-0 flex-col gap-1.5 p-2.5 text-xs">
        {scene.cameraMovement && (
          <p className="flex min-w-0 items-center gap-1.5 text-muted-foreground" title={scene.cameraMovement}>
            <Camera size={12} className="shrink-0" />
            <span className="truncate">{scene.cameraMovement}</span>
          </p>
        )}

        <p className="line-clamp-2 leading-relaxed text-foreground" title={scene.description}>
          {scene.description}
        </p>

        {scene.script && (
          <p className="line-clamp-3 rounded-md bg-muted/60 px-2 py-1.5 italic leading-relaxed text-foreground" title="Voiceover line">
            “{scene.script}”
          </p>
        )}

        {scene.sfx && (
          <p className="flex min-w-0 items-center gap-1.5 text-muted-foreground" title={`Sound effects: ${scene.sfx}`}>
            <Volume2 size={12} className="shrink-0" />
            <span className="truncate">{scene.sfx}</span>
          </p>
        )}

        <label className="flex flex-col gap-1">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Subtitle</span>
          <input
            type="text"
            value={scene.subtitle}
            onChange={(event) => onSubtitleChange(scene.index, event.target.value)}
            className="min-w-0 rounded-md border bg-background px-2 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder="On-screen caption"
          />
        </label>

        <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Clock size={11} />
          {scene.duration}s
        </p>
      </div>
    </article>
  );
}

export function VideoPlanStoryboard({
  plan,
  onContinue,
  isRendering,
}: VideoPlanStoryboardProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scenes, setScenes] = useState(plan.scenes);
  const [voiceoverType, setVoiceoverType] = useState<"elevenlabs" | "music_only" | "native_omni" | "silent">(
    plan.voiceoverType ?? "elevenlabs"
  );
  const [creativeMode, setCreativeMode] = useState<CreativeMode>(
    plan.creativeMode
      ?? (plan.voiceoverType === "music_only" || plan.voiceoverType === "silent" ? "music_first" : "voiceover")
  );
  const [factsConfirmed, setFactsConfirmed] = useState(false);
  const [localizationConfirmed, setLocalizationConfirmed] = useState(false);
  const plannedDuration = scenes.reduce((total, scene) => total + scene.duration, 0);
  const hasRequestedDuration = typeof plan.durationSec === "number" && plan.durationSec > 0;
  const durationMismatch = hasRequestedDuration && Math.abs(plannedDuration - plan.durationSec!) > 0.1;
  const gridLabel = storyboardGridLabel(scenes.length);
  const {
    missingScripts,
    missingCaptions,
    missingKeyframes,
    estimatedOmniRuns,
    runBudget,
    reserveRuns,
    overBudget,
    structurallyReady,
  } = evaluateVideoPlanReadiness(scenes, creativeMode, plan.durationSec);
  const requiresSpeech = creativeMode !== "music_first";
  const readyToRender = structurallyReady
    && factsConfirmed
    && localizationConfirmed;

  useGSAP(
    () => {
      gsap.from(".scene-card", {
        y: 20,
        autoAlpha: 0,
        stagger: 0.08,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: containerRef, dependencies: [plan.planId], revertOnUpdate: true }
  );

  const handleSubtitleChange = (index: number, value: string): void => {
    setFactsConfirmed(false);
    setLocalizationConfirmed(false);
    setScenes((previous) =>
      previous.map((scene) => (scene.index === index ? { ...scene, subtitle: value } : scene))
    );
  };

  const handleContinue = (): void => {
    if (!readyToRender) return;
    onContinue({ ...plan, scenes, voiceoverType, creativeMode });
  };

  const handleCreativeModeChange = (mode: CreativeMode): void => {
    setCreativeMode(mode);
    setVoiceoverType(mode === "music_first" ? "music_only" : "elevenlabs");
    setFactsConfirmed(false);
    setLocalizationConfirmed(false);
  };

  const handleAudioModeChange = (mode: AudioMode): void => {
    setVoiceoverType(mode);
    setFactsConfirmed(false);
    setLocalizationConfirmed(false);
  };

  return (
    <section ref={containerRef} className="flex min-w-0 flex-col gap-2.5 rounded-xl border bg-muted/20 p-3">
      <header className="flex flex-col gap-1.5 border-b pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-1.5 text-sm font-bold text-primary">
            <Clapperboard size={16} />
            Storyboard review
          </h3>
          <span className="rounded-full bg-primary/10 px-2 py-1 text-[10px] font-semibold text-primary">
            {gridLabel} · {scenes.length} scripted beats · {plan.aspectRatio}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Review the planned shots and captions before rendering. Each preview is cropped to prioritise the visual scene over the V3 grid&apos;s embedded prompt copy.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-1.5 rounded-lg border bg-card p-2 text-[11px] sm:grid-cols-4">
        <div className="min-w-0">
          <p className="text-muted-foreground">Planned runtime</p>
          <p className="font-semibold text-foreground">{plannedDuration}s</p>
        </div>
        {hasRequestedDuration && (
          <div className="min-w-0">
            <p className="text-muted-foreground">Requested</p>
            <p className="font-semibold text-foreground">{plan.durationSec}s</p>
          </div>
        )}
        <div className="min-w-0">
          <p className="text-muted-foreground">References</p>
          <p className="font-semibold text-foreground">{plan.referenceImageUrls?.length ?? 0}</p>
        </div>
        <div className="min-w-0">
          <p className="text-muted-foreground">Market</p>
          <p className="truncate font-semibold capitalize text-foreground">{plan.market ?? "Not specified"}</p>
        </div>
      </div>

      {durationMismatch && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
          The scenes total {plannedDuration}s, while the requested runtime is {plan.durationSec}s. Review this before production.
        </p>
      )}

      {plan.sceneGridUrl && (
        <figure className="overflow-hidden rounded-lg border bg-card">
          <figcaption className="flex items-center gap-1.5 border-b bg-muted/40 px-3 py-2 text-xs font-semibold text-foreground">
            <Layers3 size={13} />
            Full scene grid reference
          </figcaption>
          <img src={plan.sceneGridUrl} alt="Approved scene grid" className="max-h-80 w-full bg-muted object-contain" />
        </figure>
      )}

      <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
        {scenes.map((scene) => (
          <SceneCard key={scene.index} scene={scene} onSubtitleChange={handleSubtitleChange} />
        ))}
      </div>

      <fieldset className="rounded-lg border bg-card p-2.5 shadow-sm">
        <legend className="px-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Creative mode</legend>
        <div className="grid gap-1.5 sm:grid-cols-3">
          {CREATIVE_MODES.map((mode) => {
            const Icon = mode.icon;
            const selected = creativeMode === mode.value;
            return (
              <button
                key={mode.value}
                type="button"
                aria-pressed={selected}
                onClick={() => handleCreativeModeChange(mode.value)}
                className={`rounded-lg border p-2.5 text-left transition-colors ${
                  selected
                    ? "border-primary bg-primary/10 text-foreground ring-1 ring-primary/20"
                    : "border-border bg-background text-muted-foreground hover:border-primary/50"
                }`}
              >
                <span className="flex items-center gap-2 text-xs font-semibold">
                  <Icon size={14} className={selected ? "text-primary" : ""} />
                  {mode.label}
                </span>
                <span className="mt-1.5 block text-[11px] font-normal leading-relaxed">{mode.description}</span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-2 rounded-lg border bg-card p-2.5 shadow-sm">
        <legend className="px-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Audio treatment</legend>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md p-1 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60">
          <input
            type="radio"
            name={`voiceoverType-${plan.planId}`}
            value="elevenlabs"
            checked={voiceoverType === "elevenlabs"}
            onChange={() => handleAudioModeChange("elevenlabs")}
            disabled={creativeMode === "music_first"}
            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span>Expressive ElevenLabs v3 production</span>
            <span className="font-normal leading-snug text-muted-foreground">Emotion-directed narration, video-synchronised music, and scene-timed Foley/SFX.</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border-t p-1 pt-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60">
          <input
            type="radio"
            name={`voiceoverType-${plan.planId}`}
            value="music_only"
            checked={voiceoverType === "music_only"}
            onChange={() => handleAudioModeChange("music_only")}
            disabled={creativeMode !== "music_first"}
            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span>ElevenLabs soundtrack + SFX only</span>
            <span className="font-normal leading-snug text-muted-foreground">No narration. Matches the music to the rendered clips and layers scene-specific sound effects.</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border-t p-1 pt-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60">
          <input
            type="radio"
            name={`voiceoverType-${plan.planId}`}
            value="native_omni"
            checked={voiceoverType === "native_omni"}
            onChange={() => handleAudioModeChange("native_omni")}
            disabled={creativeMode !== "music_first"}
            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span>Native Gemini Omni audio</span>
            <span className="font-normal leading-snug text-muted-foreground">Keeps Gemini Omni ambience and sound effects; no separate narration is generated.</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border-t p-1 pt-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60">
          <input
            type="radio"
            name={`voiceoverType-${plan.planId}`}
            value="silent"
            checked={voiceoverType === "silent"}
            onChange={() => handleAudioModeChange("silent")}
            disabled={creativeMode !== "music_first"}
            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span>Silent video</span>
            <span className="font-normal leading-snug text-muted-foreground">Exports no audio so a creator can add a licensed soundtrack later.</span>
          </span>
        </label>
      </fieldset>

      <section className="rounded-lg border bg-card p-3 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="flex items-center gap-1.5 text-xs font-bold text-foreground">
              <ShieldCheck size={14} className="text-primary" />
              Production readiness
            </h4>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              Rendering is a paid step. Confirm the current storyboard before premium generation begins.
            </p>
          </div>
          <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${
            readyToRender ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-amber-500/10 text-amber-800 dark:text-amber-200"
          }`}>
            {readyToRender ? "Ready" : "Review needed"}
          </span>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {[
            { label: "Scene runtime matches request", pass: !durationMismatch },
            { label: requiresSpeech ? "Every scene has narration" : "Spoken narration is not required", pass: !missingScripts },
            { label: "Every scene has on-screen text", pass: !missingCaptions },
            { label: "Every scene has a generated visual frame", pass: !missingKeyframes },
            { label: "Estimated runs fit the budget", pass: !overBudget },
          ].map((item) => (
            <div key={item.label} className="flex items-start gap-2 rounded-md bg-muted/40 px-2.5 py-2 text-[11px]">
              {item.pass
                ? <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-emerald-600" />
                : <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-600" />}
              <span className="leading-relaxed text-foreground">{item.label}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-[11px]">
          <WalletCards size={14} className="shrink-0 text-primary" />
          <span className="text-muted-foreground">
            Estimated Omni usage: <strong className="text-foreground">{estimatedOmniRuns} of {runBudget} runs</strong>
            {" · "}{reserveRuns} run{reserveRuns === 1 ? "" : "s"} kept for correction
          </span>
        </div>

        <div className="mt-3 space-y-2">
          <label className="flex cursor-pointer items-start gap-2 text-[11px] leading-relaxed text-foreground">
            <input
              type="checkbox"
              checked={factsConfirmed}
              onChange={(event) => setFactsConfirmed(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded accent-primary"
            />
            I verified that the product facts, offer, and CTA are approved and no unsupported claims were added.
          </label>
          <label className="flex cursor-pointer items-start gap-2 text-[11px] leading-relaxed text-foreground">
            <input
              type="checkbox"
              checked={localizationConfirmed}
              onChange={(event) => setLocalizationConfirmed(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded accent-primary"
            />
            I reviewed the selected language, captions, and cultural fit for this market.
          </label>
        </div>
      </section>

      <button
        type="button"
        onClick={handleContinue}
        disabled={isRendering || !readyToRender}
        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isRendering ? (
          <><Loader2 size={15} className="animate-spin" />Rendering scenes…</>
        ) : (
          <><Play size={15} />Approve current plan and render video</>
        )}
      </button>
    </section>
  );
}

export default VideoPlanStoryboard;
