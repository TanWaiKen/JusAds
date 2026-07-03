/**
 * VideoPlanStoryboard — Video V2 storyboard review + approval (Continue gate).
 *
 * Renders the Director's planned scenes as a fan-out of shot cards (keyframe +
 * shot type, camera movement, subtitle, script, SFX, duration), mirroring a
 * pro storyboard board. The user reviews (and can lightly edit subtitles) then
 * clicks Continue to run the expensive Veo render. Nothing is generated until
 * Continue is pressed.
 */

import React, { useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { Clapperboard, Camera, Volume2, Clock, Play, Loader2 } from "lucide-react";
import type { VideoPlan } from "@/services/generationApi";

gsap.registerPlugin(useGSAP);

interface VideoPlanStoryboardProps {
  plan: VideoPlan;
  onContinue: (plan: VideoPlan) => void;
  isRendering: boolean;
}

/** A single storyboard shot card. */
function SceneCard({
  scene,
  onSubtitleChange,
}: {
  scene: VideoPlan["scenes"][number];
  onSubtitleChange: (index: number, value: string) => void;
}): React.ReactElement {
  return (
    <div className="scene-card flex w-56 shrink-0 flex-col overflow-hidden rounded-lg border bg-card shadow-sm">
      {/* Keyframe */}
      <div className="relative">
        {scene.keyframeUrl ? (
          <img
            src={scene.keyframeUrl}
            alt={`Scene ${scene.index + 1}`}
            className="h-32 w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-32 w-full items-center justify-center bg-muted text-xs text-muted-foreground">
            No keyframe
          </div>
        )}
        <span className="absolute left-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-bold text-white">
          {scene.index + 1}
        </span>
        {scene.shotType && (
          <span className="absolute right-1.5 top-1.5 rounded bg-primary/80 px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
            {scene.shotType}
          </span>
        )}
      </div>

      {/* Meta */}
      <div className="flex flex-col gap-1.5 p-2.5 text-[11px]">
        {scene.cameraMovement && (
          <p className="flex items-center gap-1 text-muted-foreground">
            <Camera size={11} className="shrink-0" />
            <span className="truncate">{scene.cameraMovement}</span>
          </p>
        )}

        <p className="line-clamp-2 text-foreground" title={scene.description}>
          {scene.description}
        </p>

        {scene.script && (
          <p className="rounded bg-muted/60 px-1.5 py-1 italic text-foreground" title="Voiceover line">
            “{scene.script}”
          </p>
        )}

        {scene.sfx && (
          <p className="flex items-center gap-1 text-muted-foreground" title="Sound effects">
            <Volume2 size={11} className="shrink-0" />
            <span className="truncate">{scene.sfx}</span>
          </p>
        )}

        {/* Editable subtitle (burnt in) */}
        <label className="mt-1 flex flex-col gap-0.5">
          <span className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
            Subtitle (editable)
          </span>
          <input
            type="text"
            value={scene.subtitle}
            onChange={(e) => onSubtitleChange(scene.index, e.target.value)}
            className="rounded border bg-background px-1.5 py-1 text-[11px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder="On-screen caption"
          />
        </label>

        <p className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <Clock size={10} />
          {scene.duration}s
        </p>
      </div>
    </div>
  );
}

export function VideoPlanStoryboard({
  plan,
  onContinue,
  isRendering,
}: VideoPlanStoryboardProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scenes, setScenes] = useState(plan.scenes);

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
    { scope: containerRef, dependencies: [plan.planId] }
  );

  const handleSubtitleChange = (index: number, value: string): void => {
    setScenes((prev) =>
      prev.map((s) => (s.index === index ? { ...s, subtitle: value } : s))
    );
  };

  const handleContinue = (): void => {
    onContinue({ ...plan, scenes });
  };

  return (
    <div ref={containerRef} className="flex flex-col gap-3 rounded-lg border bg-muted/20 p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-bold text-primary">
          <Clapperboard size={15} />
          Storyboard — {scenes.length} scenes
          <span className="text-xs font-normal text-muted-foreground">({plan.aspectRatio})</span>
        </h3>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Review the planned scenes and tweak any subtitle. Click Continue to render each scene with
        Veo (this is the slow step).
      </p>

      {/* Horizontal storyboard strip */}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {scenes.map((scene) => (
          <SceneCard key={scene.index} scene={scene} onSubtitleChange={handleSubtitleChange} />
        ))}
      </div>

      <button
        type="button"
        onClick={handleContinue}
        disabled={isRendering}
        className="inline-flex items-center justify-center gap-2 self-start rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isRendering ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            Rendering scenes...
          </>
        ) : (
          <>
            <Play size={14} />
            Continue — Render Video
          </>
        )}
      </button>
    </div>
  );
}

export default VideoPlanStoryboard;
