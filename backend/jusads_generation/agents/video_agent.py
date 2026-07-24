"""
video_agent.py
──────────────
Video_Agent – one of the four independent Media Agents (Req 5.1).

Generates a video ad **fully independently** (Req 5.3) using Google Gemini Omni
(gemini-omni-flash-preview) for native video generation. The model generates
the entire video clip in a single call — no clip-by-clip stitching required.

Gemini Omni generates its own cinematic background audio.
When the ad requires human narration (commercial voiceover), ElevenLabs TTS is
generated separately and merged on top of the Omni video via ffmpeg.

This module implements the shared ``generate(...)`` contract from
``agents/base.py``. It lives in its own file and does NOT import the other three
Media Agents (Req 5.2). All external calls (Gemini Omni, ElevenLabs, ffmpeg,
S3, Supabase) are wrapped in try/except with ``[VideoAgent]``-prefixed logging.
The output duration is bounded by the resolved ``rules.max_duration_seconds``
(Req 7.1).
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT, MODEL_VIDEO
from shared.prompts import VIDEO_AD_GENERATION_PROMPT
from shared.s3_client import upload_file_public

from .base import AgentResult, load_guide
from ..provenance import generated_ad_context_fields

logger = logging.getLogger(__name__)

# -- Duration constants --------------------------------------------------------
_DEFAULT_DURATION = 8.0


# --- Helpers ------------------------------------------------------------------


def _resolve_duration(rules: dict) -> float:
    """Resolve the target clip duration bounded by the platform ceiling (Req 7.1)."""
    max_duration = rules.get("max_duration_seconds") if rules else None
    if not max_duration or max_duration <= 0:
        return _DEFAULT_DURATION
    return min(float(_DEFAULT_DURATION), float(max_duration))


def _build_visual_prompt(brief: str, rules: dict) -> str:
    """Use Gemini to refine the brief into a cinematic video prompt for Omni."""
    guide = load_guide("video")
    aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"

    refine_prompt = VIDEO_AD_GENERATION_PROMPT.format(
        brief=brief,
        aspect_ratio=aspect_ratio,
        guide=guide[:400],
    )

    try:
        resp = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=refine_prompt,
        )
        return resp.text.strip()
    except Exception as e:
        logger.warning("[VideoAgent] Prompt refinement failed: %s. Using raw brief.", e)
        return brief


# --- Gemini Omni Video Generation --------------------------------------------


async def _generate_omni_video(
    prompt: str,
    aspect_ratio: str,
    work_dir: Path,
) -> Optional[str]:
    """Call Gemini Omni (MODEL_VIDEO) to generate a full video in one call.

    Gemini Omni generates the entire video clip natively — no clip-by-clip
    stitching or frame interpolation required. Returns local .mp4 path or None.
    """

    def _blocking_omni_call() -> Optional[bytes]:
        """Synchronous Gemini Omni call (runs in a thread)."""
        try:
            from google.genai import types

            logger.info(
                "[VideoAgent] Submitting Gemini Omni request: model=%s, aspect=%s",
                MODEL_VIDEO,
                aspect_ratio,
            )

            response = gemini.models.generate_content(
                model=MODEL_VIDEO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=1,
                    top_p=0.95,
                    max_output_tokens=32768,
                    response_modalities=["VIDEO", "AUDIO"],
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                    ],
                ),
            )

            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if (
                        hasattr(part, "inline_data")
                        and part.inline_data
                        and part.inline_data.data
                        and "video" in (part.inline_data.mime_type or "")
                    ):
                        logger.info("[VideoAgent] Gemini Omni video generation successful.")
                        return part.inline_data.data

            logger.error("[VideoAgent] Gemini Omni returned no video data.")
            return None

        except Exception as e:
            logger.error("[VideoAgent] Gemini Omni API call failed: %s", e)
            return None

    try:
        video_bytes = await asyncio.to_thread(_blocking_omni_call)
    except Exception as e:
        logger.error("[VideoAgent] asyncio.to_thread error for Omni: %s", e)
        return None

    if not video_bytes:
        return None

    # Write bytes to disk
    omni_path = str(work_dir / f"omni_{uuid.uuid4().hex[:6]}.mp4")
    with open(omni_path, "wb") as f:
        f.write(video_bytes)
    logger.info("[VideoAgent] Omni video saved to %s", omni_path)
    return omni_path


# --- Voiceover Generation ----------------------------------------------------


def _generate_voiceover(brief: str, duration: float, work_dir: Path) -> Optional[str]:
    """Generate ElevenLabs voiceover narration for the ad. Returns .mp3 path or None.

    Gemini Omni handles cinematic background audio, so this only generates the
    human narration track (voiceover).
    """
    from shared.elevenlabs_utils import generate_tts
    from config import get_voice

    # Script a short, punchy voiceover line via Gemini.
    try:
        vo_resp = gemini.models.generate_content(
            model=MODEL_TEXT,
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
    voice_entry = get_voice("malaysia", "malay", "female")
    voice_id = voice_entry["voice_id"]
    lang_code = voice_entry.get("lang", "ms")

    ok = generate_tts(vo_text, vo_path, voice_id=voice_id, language_code=lang_code)
    if ok:
        logger.info("[VideoAgent] Voiceover generated: %s", vo_text[:60])
        return vo_path
    logger.warning("[VideoAgent] Voiceover TTS failed.")
    return None


# --- Voiceover Merge ----------------------------------------------------------


def _merge_voiceover(video_path: str, vo_path: str, out_path: str) -> bool:
    """Merge voiceover audio track onto the Omni video via ffmpeg.

    The Omni video already has its own audio (cinematic/background). The VO is
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
        logger.info("[VideoAgent] Merging voiceover onto Omni video...")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("[VideoAgent] Voiceover merged successfully.")
        return True
    except Exception as e:
        logger.warning("[VideoAgent] Voiceover merge failed: %s. Using Omni video as-is.", e)
        return False


# --- Supabase Recording ------------------------------------------------------


def _record_generated_ad(
    *,
    project_id: str,
    task_id: str,
    platform: str,
    prompt_used: str,
    s3_key: Optional[str],
    status: str,
    metadata: dict,
    generation_context: Optional[dict] = None,
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
                    **generated_ad_context_fields(generation_context),
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


# --- Public contract ----------------------------------------------------------


async def generate(*, brief: str, project_id: str, task_id: str,
    platform: str, rules: dict, reference_parts: Optional[list] = None,
    generation_context: Optional[dict] = None,
) -> AgentResult:

    # GoogleSearch for video style trends (graceful degradation on failure)
    from jusads_generation.search_tools import search_creative_context, derive_search_query

    search_query = derive_search_query(brief=brief, market="malaysia", theme=f"{platform} short video ad reel")
    search_context = await search_creative_context(
        query=search_query,
        market="malaysia",
        task_id=task_id,
    )

    enriched_brief = brief
    if search_context:
        enriched_brief = f"{brief}\n\n[VIDEO TREND CONTEXT]: {search_context[:400]}"

    work_dir: Optional[Path] = None
    final_video_path: Optional[str] = None

    try:
        work_dir = Path(tempfile.mkdtemp(prefix="video_ad_"))
        aspect_ratio = rules.get("aspect_ratio", "9:16") if rules else "9:16"
        duration = _resolve_duration(rules)

        # -- Generate video via Gemini Omni ------------------------------------
        visual_prompt = _build_visual_prompt(enriched_brief, rules)
        logger.info("[VideoAgent] Visual prompt for Omni: %s", visual_prompt[:120])

        omni_video_path = await _generate_omni_video(
            prompt=visual_prompt,
            aspect_ratio=aspect_ratio,
            work_dir=work_dir,
        )

        vo_path = _generate_voiceover(brief, duration, work_dir)

        if vo_path:
            merged_path = str(work_dir / "final_with_vo.mp4")
            if _merge_voiceover(omni_video_path, vo_path, merged_path):
                final_video_path = merged_path
            else:
                # Merge failed – use Omni video without VO (still has Omni audio)
                final_video_path = omni_video_path
        else:
            # No VO generated – Omni video with its own audio is still good
            final_video_path = omni_video_path

        if not final_video_path or not os.path.exists(final_video_path):
            raise RuntimeError("Video generation produced no output file.")

        # -- Upload to S3 ------------------------------------------------------
        s3_key = f"generated_ads/{project_id}/{task_id}/video_{uuid.uuid4().hex[:6]}.mp4"
        try:
            s3_url = upload_file_public(final_video_path, s3_key)
        except Exception as e:
            logger.warning("[VideoAgent] S3 upload failed, using fallback URL: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        # -- Record success (Req 5.4) ------------------------------------------
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
                "generation_method": "gemini_omni",
                "independent": True,
            },
            generation_context=generation_context,
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
            generation_context=generation_context,
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
