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
import { Clapperboard, Camera, Volume2, Clock, Play, Loader2, Grid3X3, Layers3 } from "lucide-react";
import type { VideoPlan } from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

interface VideoPlanStoryboardProps {
  plan: VideoPlan;
  onContinue: (plan: VideoPlan) => void;
  isRendering: boolean;
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
    <article className="scene-card min-w-0 overflow-hidden rounded-xl border bg-card shadow-sm">
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

      <div className="flex min-w-0 flex-col gap-2 p-3 text-xs">
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

        <label className="mt-1 flex flex-col gap-1">
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
  const [voiceoverType, setVoiceoverType] = useState<"elevenlabs" | "omni">(
    plan.voiceoverType ?? "elevenlabs"
  );
  const plannedDuration = scenes.reduce((total, scene) => total + scene.duration, 0);
  const hasRequestedDuration = typeof plan.durationSec === "number" && plan.durationSec > 0;
  const durationMismatch = hasRequestedDuration && Math.abs(plannedDuration - plan.durationSec!) > 0.1;

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
    setScenes((previous) =>
      previous.map((scene) => (scene.index === index ? { ...scene, subtitle: value } : scene))
    );
  };

  const handleContinue = (): void => {
    onContinue({ ...plan, scenes, voiceoverType });
  };

  return (
    <section ref={containerRef} className="flex min-w-0 flex-col gap-4 rounded-xl border bg-muted/20 p-3 sm:p-4">
      <header className="flex flex-col gap-2 border-b pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-1.5 text-sm font-bold text-primary">
            <Clapperboard size={16} />
            Storyboard review
          </h3>
          <span className="rounded-full bg-primary/10 px-2 py-1 text-[10px] font-semibold text-primary">
            {scenes.length} scenes · {plan.aspectRatio}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Review the planned shots and captions before rendering. Each preview is cropped to prioritise the visual scene over the V3 grid&apos;s embedded prompt copy.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-2 rounded-lg border bg-card p-2.5 text-[11px] sm:grid-cols-4">
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

      <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
        {scenes.map((scene) => (
          <SceneCard key={scene.index} scene={scene} onSubtitleChange={handleSubtitleChange} />
        ))}
      </div>

      <fieldset className="flex flex-col gap-3 rounded-lg border bg-card p-3 shadow-sm">
        <legend className="px-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Audio treatment</legend>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md p-1 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60">
          <input
            type="radio"
            name={`voiceoverType-${plan.planId}`}
            value="elevenlabs"
            checked={voiceoverType === "elevenlabs"}
            onChange={() => setVoiceoverType("elevenlabs")}
            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span>Premium ElevenLabs narration</span>
            <span className="font-normal leading-snug text-muted-foreground">Uses the storyboard script for spoken narration, mixed with backing audio.</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border-t p-1 pt-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted/60">
          <input
            type="radio"
            name={`voiceoverType-${plan.planId}`}
            value="omni"
            checked={voiceoverType === "omni"}
            onChange={() => setVoiceoverType("omni")}
            className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
          />
          <span className="flex flex-col gap-0.5">
            <span>Native Gemini Omni audio</span>
            <span className="font-normal leading-snug text-muted-foreground">Uses native ambience and sound effects without a separate narration overlay.</span>
          </span>
        </label>
      </fieldset>

      <button
        type="button"
        onClick={handleContinue}
        disabled={isRendering}
        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isRendering ? (
          <><Loader2 size={15} className="animate-spin" />Rendering scenes…</>
        ) : (
          <><Play size={15} />Approve plan and render video</>
        )}
      </button>
    </section>
  );
}

export default VideoPlanStoryboard;
