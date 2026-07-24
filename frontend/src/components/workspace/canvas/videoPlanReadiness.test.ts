import { describe, expect, it } from "vitest";
import type { VideoPlanScene } from "@/services/generationApi";
import { evaluateVideoPlanReadiness } from "./videoPlanReadiness";

function scene(overrides: Partial<VideoPlanScene> = {}): VideoPlanScene {
  return {
    index: 0,
    description: "Product reveal",
    shotType: "Close-up",
    cameraMovement: "Push in",
    subtitle: "Learn more",
    script: "Meet Acme.",
    sfx: "",
    duration: 5,
    keyframeS3Key: "",
    keyframeUrl: "https://cdn.example.com/frame-01.png",
    ...overrides,
  };
}

describe("evaluateVideoPlanReadiness", () => {
  it("requires narration for speaker-led and voiceover video", () => {
    expect(evaluateVideoPlanReadiness([scene({ script: "" })], "speaker_led", 5).missingScripts).toBe(true);
    expect(evaluateVideoPlanReadiness([scene({ script: "" })], "voiceover", 5).missingScripts).toBe(true);
  });

  it("does not block music-first video when narration is empty", () => {
    const result = evaluateVideoPlanReadiness([scene({ script: "" })], "music_first", 5);
    expect(result.missingScripts).toBe(false);
    expect(result.structurallyReady).toBe(true);
  });

  it("still requires on-screen text in music-first mode", () => {
    const result = evaluateVideoPlanReadiness([scene({ script: "", subtitle: "" })], "music_first", 5);
    expect(result.missingCaptions).toBe(true);
    expect(result.structurallyReady).toBe(false);
  });

  it("blocks rendering when any generated scene frame is missing", () => {
    const result = evaluateVideoPlanReadiness(
      [scene(), scene({ index: 1, keyframeUrl: "" })],
      "music_first",
      10,
    );
    expect(result.missingKeyframes).toBe(true);
    expect(result.structurallyReady).toBe(false);
  });

  it("blocks duration mismatches and plans within the ten-run budget", () => {
    const scenes = [scene(), scene({ index: 1 })];
    const result = evaluateVideoPlanReadiness(scenes, "voiceover", 15);
    expect(result.durationMismatch).toBe(true);
    expect(result.estimatedOmniRuns).toBe(1);
    expect(result.reserveRuns).toBe(9);
    expect(result.structurallyReady).toBe(false);
  });
});
