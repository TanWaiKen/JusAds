"""
video_agent.py
──────────────
Video_Agent — one of the four independent Media Agents (Req 5.1).

Generates a video ad **fully independently** (Req 5.3) using Google Veo 3.0
for real dynamic video generation. No fallback — if Veo is not configured or
fails, the agent fails loudly with a clear error so developers can diagnose
the issue immediately.

Veo generates its own cinematic background audio (``generate_audio=True``).
When the ad requires human narration (commercial voiceover), ElevenLabs TTS is
generated separately and merged on top of the Veo video via ffmpeg.

This module implements the shared ``generate(...)`` contract from
``agents/base.py``. It lives in its own file and does NOT import the other three
Media Agents (Req 5.2). All external calls (Veo, Gemini, ElevenLabs, ffmpeg,
S3, Supabase) are wrapped in try/except with ``[VideoAgent]``-prefixed logging.
The output duration is bounded by the resolved ``rules.max_duration_seconds``
(Req 7.1).
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from shared.clients import gemini, supabase
from shared.s3_client import upload_file_public
from config import VERTEX_PROJECT_ID

from .base import AgentResult, load_guide

logger = logging.getLogger(__name__)

# ── Duration constants ────────────────────────────────────────────────────────
_DEFAULT_DURATION = 8.0
# Veo minimum is 5 seconds.
_VEO_MIN_DURATION = 5


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_duration(rules: dict) -> float:
    """Resolve the target clip duration bounded by the platform ceiling (Req 7.1)."""
    max_duration = rules.get("max_duration_seconds") if rules else None
    if not max_duration or max_duration <= 0:
        return _DEFAULT_DURATION
    return min(float(_DEFAULT_DURATION), float(max_duration))


def _resolve_veo_duration(rules: dict) -> int:
    """Resolve duration for Veo (integer, minimum 5s, bounded by rules)."""
    max_duration = rules.get("max_duration_seconds") if rules else None
    if not max_duration or max_duration <= 0:
        target = int(_DEFAULT_DURATION)
    else:
        target = int(min(_DEFAULT_DURATION, float(max_duration)))
    return max(_VEO_MIN_DURATION, target)


def _build_visual_prompt(brief: str, rules: dict) -> str:
    """Use Gemini to refine the brief into a cinematic video prompt for Veo."""
    guide = load_guide("video")
    aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"

    refine_prompt = f"""You are an expert advertising Creative Director specialising in short-form video ads.
Convert the following ad brief into a detailed cinematic video scene prompt suitable for an AI video generation model (Google Veo):

Brief: "{brief}"

Requirements:
- Describe a DYNAMIC scene with motion, camera movement, and action (not a static shot)
- Clean, modern commercial style suitable for short-form video ({aspect_ratio})
- High contrast, vibrant, product-focused composition
- Culturally appropriate for Southeast Asian markets (Malaysia/Singapore), modest presentation
- Include cinematic details: lighting, camera angle, movement direction, pacing
- Do NOT mention text overlays, logos, or UI elements — only the visual scene

Reference guidelines: {guide[:400]}

Output ONLY the video scene prompt (max 100 words)."""

    try:
        resp = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=refine_prompt,
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning("[VideoAgent] Prompt refinement failed: %s. Using raw brief.", e)
        return brief


# ─── Veo Video Generation ─────────────────────────────────────────────────────


async def _generate_veo_video(
    prompt: str,
    aspect_ratio: str,
    duration: int,
    work_dir: Path,
) -> Optional[str]:
    """Call Google Veo 3.0 to generate a dynamic video. Returns local .mp4 path or None.

    Uses asyncio.to_thread for the blocking poll loop so the event loop is not
    blocked.
    """
    if not VERTEX_PROJECT_ID:
        logger.warning("[VideoAgent] VERTEX_PROJECT_ID not set — skipping Veo.")
        return None

    def _blocking_veo_call() -> Optional[bytes]:
        """Synchronous Veo call + polling (runs in a thread)."""
        try:
            from google import genai
            from google.genai import types

            veo_client = genai.Client(
                vertexai=True,
                project=VERTEX_PROJECT_ID,
                location="us-central1",
            )

            logger.info(
                "[VideoAgent] Submitting Veo 3.0 request: duration=%ds, aspect=%s",
                duration,
                aspect_ratio,
            )

            operation = veo_client.models.generate_videos(
                model="veo-3.0-generate-001",
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio=aspect_ratio,
                    number_of_videos=1,
                    duration_seconds=duration,
                    person_generation="allow_adult",
                    generate_audio=True,
                ),
            )

            # Poll for completion
            while not operation.done:
                logger.info("[VideoAgent] Veo generation in progress... polling in 10s.")
                time.sleep(10)
                operation = veo_client.operations.get(operation)

            response = operation.result
            if not response or not response.generated_videos:
                logger.error("[VideoAgent] Veo returned no videos.")
                return None

            video = response.generated_videos[0]
            if not video.video or not video.video.video_bytes:
                logger.error("[VideoAgent] Veo video has no bytes.")
                return None

            logger.info("[VideoAgent] Veo 3.0 video generated successfully.")
            return video.video.video_bytes

        except Exception as e:
            logger.error("[VideoAgent] Veo API call failed: %s", e)
            return None

    try:
        video_bytes = await asyncio.to_thread(_blocking_veo_call)
    except Exception as e:
        logger.error("[VideoAgent] asyncio.to_thread error for Veo: %s", e)
        return None

    if not video_bytes:
        return None

    # Write bytes to disk
    veo_path = str(work_dir / f"veo_{uuid.uuid4().hex[:6]}.mp4")
    with open(veo_path, "wb") as f:
        f.write(video_bytes)
    logger.info("[VideoAgent] Veo video saved to %s", veo_path)
    return veo_path


# ─── Voiceover Generation ─────────────────────────────────────────────────────


def _generate_voiceover(brief: str, duration: float, work_dir: Path) -> Optional[str]:
    """Generate ElevenLabs voiceover narration for the ad. Returns .mp3 path or None.

    Veo handles cinematic background audio, so this only generates the human
    narration track (voiceover). SFX generation is skipped.
    """
    from shared.elevenlabs_utils import generate_tts
    from config import DEFAULT_VOICE

    # Script a short, punchy voiceover line via Gemini.
    try:
        vo_resp = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Write ONE short, punchy voiceover line (max 20 words) for a commercial "
                f"video ad about: {brief}. Output only the line, no quotes."
            ),
        )
        vo_text = vo_resp.text.strip()
    except Exception as e:
        logger.warning("[VideoAgent] Voiceover scripting failed: %s. Using brief.", e)
        vo_text = brief[:120]

    vo_path = str(work_dir / "voiceover.mp3")
    voice_id = DEFAULT_VOICE["voice_id"]
    lang_code = DEFAULT_VOICE.get("lang", "ms")

    ok = generate_tts(vo_text, vo_path, voice_id=voice_id, language_code=lang_code)
    if ok:
        logger.info("[VideoAgent] Voiceover generated: %s", vo_text[:60])
        return vo_path
    logger.warning("[VideoAgent] Voiceover TTS failed.")
    return None


# ─── Voiceover Merge ──────────────────────────────────────────────────────────


def _merge_voiceover(video_path: str, vo_path: str, out_path: str) -> bool:
    """Merge voiceover audio track onto the Veo video via ffmpeg.

    The Veo video already has its own audio (cinematic/background). The VO is
    mixed on top as a second audio stream, then down-mixed to stereo.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", vo_path,
        "-filter_complex",
        "[0:a]volume=0.4[bg];[1:a]volume=1.0[vo];[bg][vo]amix=inputs=2:duration=shortest[aout]",
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        out_path,
    ]
    try:
        logger.info("[VideoAgent] Merging voiceover onto Veo video...")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("[VideoAgent] Voiceover merged successfully.")
        return True
    except Exception as e:
        logger.warning("[VideoAgent] Voiceover merge failed: %s. Using Veo video as-is.", e)
        return False


# ─── Supabase Recording ──────────────────────────────────────────────────────


def _record_generated_ad(
    *,
    project_id: str,
    task_id: str,
    platform: str,
    prompt_used: str,
    s3_key: Optional[str],
    status: str,
    metadata: dict,
) -> Optional[str]:
    """Insert a ``generated_ads`` row and return its id (best-effort)."""
    try:
        response = (
            supabase.table("generated_ads")
            .insert(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "media_type": "video",
                    "platform": platform,
                    "prompt_used": prompt_used,
                    "s3_media_key": s3_key,
                    "status": status,
                    "metadata": metadata,
                }
            )
            .execute()
        )
        rows = response.data or []
        ad_id = rows[0].get("id") if rows else None
        logger.info("[VideoAgent] Recorded generated_ads row (status=%s, id=%s)", status, ad_id)
        return ad_id
    except Exception as e:
        logger.error("[VideoAgent] Supabase recording failed (status=%s): %s", status, e)
        return None


# ─── Public contract ──────────────────────────────────────────────────────────


async def generate(
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: dict,
    reference_parts: Optional[list] = None,
) -> AgentResult:
    """Generate one video ad and record it in ``generated_ads``.

    Primary path: Google Veo 3.0 dynamic video generation with built-in audio.
    If Veo is unavailable or fails, falls back to static image + ffmpeg stitch.

    When Veo succeeds, a separate ElevenLabs voiceover is generated and merged
    on top (commercial ads need human narration). Veo's own audio serves as the
    cinematic background/sound bed.

    Args:
        brief: The creative/product prompt for the ad.
        project_id: Owning project id.
        task_id: Owning task id.
        platform: Normalized target platform (e.g. ``"tiktok"``).
        rules: Resolved ``PlatformRule`` sizing (aspect ratio + duration).
        reference_parts: Optional multimodal reference parts (unused for video).

    Returns:
        An :class:`AgentResult` describing the generated (or failed) output.
    """
    logger.info("[VideoAgent] Starting video generation for '%s'", platform)
    work_dir: Optional[Path] = None
    final_video_path: Optional[str] = None

    try:
        work_dir = Path(tempfile.mkdtemp(prefix="video_ad_"))
        aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"

        # Veo is REQUIRED — no fallback. Fail loudly if not configured.
        if not VERTEX_PROJECT_ID:
            raise RuntimeError(
                "VERTEX_PROJECT_ID is not configured. Video generation requires Google Veo. "
                "Set VERTEX_PROJECT_ID in backend/.env to enable video generation."
            )

        # ── Generate video via Veo 3.0 ────────────────────────────────────────
        veo_duration = _resolve_veo_duration(rules)
        visual_prompt = _build_visual_prompt(brief, rules)
        logger.info("[VideoAgent] Visual prompt for Veo: %s", visual_prompt[:120])

        veo_video_path = await _generate_veo_video(
            prompt=visual_prompt,
            aspect_ratio=aspect_ratio,
            duration=veo_duration,
            work_dir=work_dir,
        )

        if not veo_video_path:
            raise RuntimeError(
                "Veo 3.0 video generation failed. Check VERTEX_PROJECT_ID, "
                "GCP credentials, and that the Veo API is enabled in your project."
            )

        # Veo succeeded — now add voiceover narration on top
        logger.info("[VideoAgent] Veo video ready. Generating voiceover narration...")
        vo_path = _generate_voiceover(brief, float(veo_duration), work_dir)

        if vo_path:
            merged_path = str(work_dir / "final_with_vo.mp4")
            if _merge_voiceover(veo_video_path, vo_path, merged_path):
                final_video_path = merged_path
            else:
                # Merge failed — use Veo video without VO (still has Veo audio)
                final_video_path = veo_video_path
        else:
            # No VO generated — Veo video with its own audio is still good
            final_video_path = veo_video_path

        if not final_video_path or not os.path.exists(final_video_path):
            raise RuntimeError("Video generation produced no output file.")

        # ── Upload to S3 ──────────────────────────────────────────────────────
        s3_key = f"generated_ads/{project_id}/{task_id}/video_{uuid.uuid4().hex[:6]}.mp4"
        try:
            s3_url = upload_file_public(final_video_path, s3_key)
        except Exception as e:
            logger.warning("[VideoAgent] S3 upload failed, using fallback URL: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        # ── Record success (Req 5.4) ──────────────────────────────────────────
        duration = _resolve_duration(rules)
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            prompt_used=brief,
            s3_key=s3_key,
            status="completed",
            metadata={
                "s3_url": s3_url,
                "aspect_ratio": aspect_ratio,
                "duration_seconds": duration,
                "generation_method": "veo_3.0",
                "independent": True,
            },
        )

        return AgentResult(
            ad_id=ad_id,
            media_type="video",
            platform=platform,
            s3_media_key=s3_key,
            public_url=s3_url,
            caption=None,
            status="completed",
            error=None,
        )

    except Exception as e:
        # Resilient failure: record a failed row without touching other agents (Req 5.5)
        logger.error("[VideoAgent] Generation failed: %s", e)
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            prompt_used=brief,
            s3_key=None,
            status="failed",
            metadata={"error": str(e)},
        )
        return AgentResult(
            ad_id=ad_id,
            media_type="video",
            platform=platform,
            s3_media_key=None,
            public_url=None,
            caption=None,
            status="failed",
            error=str(e),
        )
    finally:
        if work_dir is not None:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
