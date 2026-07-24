import type { VideoPlan, VideoPlanScene } from "@/services/generationApi";

export interface VideoPlanReadiness {
  durationMismatch: boolean;
  missingScripts: boolean;
  missingCaptions: boolean;
  missingKeyframes: boolean;
  estimatedOmniRuns: number;
  runBudget: number;
  reserveRuns: number;
  overBudget: boolean;
  structurallyReady: boolean;
}

export function evaluateVideoPlanReadiness(
  scenes: VideoPlanScene[],
  creativeMode: NonNullable<VideoPlan["creativeMode"]>,
  requestedDuration?: number,
  runBudget = 10,
): VideoPlanReadiness {
  const plannedDuration = scenes.reduce((total, scene) => total + scene.duration, 0);
  const hasRequestedDuration = typeof requestedDuration === "number" && requestedDuration > 0;
  const durationMismatch = hasRequestedDuration && Math.abs(plannedDuration - requestedDuration) > 0.1;
  const requiresSpeech = creativeMode !== "music_first";
  const missingScripts = requiresSpeech && scenes.some((scene) => !scene.script.trim());
  const missingCaptions = scenes.some((scene) => !scene.subtitle.trim());
  const missingKeyframes = scenes.some((scene) => !scene.keyframeUrl.trim());
  // Production groups adjacent five-second scenes into Omni segments of up to
  // ten seconds, so estimate the paid calls from runtime rather than card count.
  const estimatedOmniRuns = Math.max(1, Math.ceil(plannedDuration / 10));
  const reserveRuns = Math.max(0, runBudget - estimatedOmniRuns);
  const overBudget = estimatedOmniRuns >= runBudget;

  return {
    durationMismatch,
    missingScripts,
    missingCaptions,
    missingKeyframes,
    estimatedOmniRuns,
    runBudget,
    reserveRuns,
    overBudget,
    structurallyReady: !durationMismatch
      && !missingScripts
      && !missingCaptions
      && !missingKeyframes
      && !overBudget,
  };
}
