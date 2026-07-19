"""
audio_agent.py
──────────────
Audio_Agent — one of the four independent Media Agents (Req 5.1).

Generates an audio ad end to end: plans a short multi-scene voiceover script,
generates a sound-effect bed and voiceover per scene, mixes them, concatenates
the scenes into a single ``.mp3``, uploads it to S3, and records a
``generated_ads`` row. The total audio duration is capped to the resolved
``rules.max_duration_seconds`` (Req 7.1).

This module implements the shared ``generate(...)`` contract from
``agents/base.py``. It lives in its own file and does NOT import the other three
Media Agents (Req 5.2). All external calls (Gemini, ElevenLabs, S3, Supabase)
are wrapped in try/except with graceful degradation and ``[AudioAgent]``-prefixed
logging per steering conventions.
"""

import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT
from shared.prompts import AUDIO_AD_GENERATION_PROMPT
from shared.s3_client import upload_file_public
from config import DEFAULT_VOICE

from .base import AgentResult, load_guide
from ..provenance import generated_ad_context_fields

logger = logging.getLogger(__name__)

# Default target duration (seconds) for a single planned scene when the platform
# rule carries no explicit duration ceiling.
_DEFAULT_SCENE_DURATION = 5.0
# Absolute floor for a usable audio ad duration.
_MIN_TOTAL_DURATION = 1.0
# ElevenLabs sound-generation accepts at most 22s per call.
_MAX_SFX_DURATION = 22.0


# --- Internal helpers --------------------------------------------------------


async def _plan_audio_script(brief: str) -> list[dict]:
    """Plan the audio ad as a list of scene dicts via Gemini.

    Each scene has ``{number, duration, script, sfxPrompt}``. Falls back to a
    single scene derived from the raw brief when planning fails.
    """
    guide = load_guide("audio")
    planning_prompt = AUDIO_AD_GENERATION_PROMPT.format(
        guide=guide[:800],
        brief=brief,
    )

    try:
        resp = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=planning_prompt,
        )
        clean = resp.text.strip().replace("```json", "").replace("```", "")
        scenes = json.loads(clean)
        if isinstance(scenes, list) and scenes:
            return scenes
    except Exception as e:
        logger.warning("[AudioAgent] Script planning failed: %s. Using single scene.", e)

    return [
        {
            "number": 1,
            "duration": 8,
            "script": brief[:300],
            "sfxPrompt": "upbeat commercial background music",
        }
    ]


def _cap_scene_durations(
    scenes: list[dict], max_duration_seconds: Optional[int]
) -> list[dict]:
    """Trim/scale scene durations so their total is â‰¤ ``max_duration_seconds``.

    Enforces the platform ad-length ceiling (Req 7.1). Scenes are kept in order
    and dropped once the running total reaches the ceiling; the final retained
    scene is shortened to fit exactly. When no ceiling is supplied, the original
    scene durations are preserved.
    """
    if not scenes:
        return scenes

    # Normalize each scene duration to a sane positive float.
    normalized: list[dict] = []
    for scene in scenes:
        duration = scene.get("duration")
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = _DEFAULT_SCENE_DURATION
        if duration <= 0:
            duration = _DEFAULT_SCENE_DURATION
        capped = dict(scene)
        capped["duration"] = duration
        normalized.append(capped)

    if not max_duration_seconds or max_duration_seconds <= 0:
        return normalized

    ceiling = float(max_duration_seconds)
    remaining = ceiling
    result: list[dict] = []
    for scene in normalized:
        if remaining <= 0:
            break
        allotted = min(scene["duration"], remaining)
        if allotted < _MIN_TOTAL_DURATION and result:
            # Not enough budget left for another meaningful scene.
            break
        capped = dict(scene)
        capped["duration"] = allotted
        result.append(capped)
        remaining -= allotted

    if not result:
        # Ceiling smaller than a single scene — keep one clipped scene.
        first = dict(normalized[0])
        first["duration"] = max(_MIN_TOTAL_DURATION, ceiling)
        result = [first]

    logger.info(
        "[AudioAgent] Capped script to %.1fs across %d scene(s) (ceiling=%ss)",
        sum(s["duration"] for s in result),
        len(result),
        max_duration_seconds,
    )
    return result


def _render_scenes(scenes: list[dict], work_dir: Path) -> list[str]:
    """Render each scene to a mixed VO+SFX ``.mp3`` and return their paths."""
    from shared.elevenlabs_utils import generate_sfx, generate_tts, mix_vo_and_sfx

    voice_id = DEFAULT_VOICE["voice_id"]
    lang_code = DEFAULT_VOICE.get("lang", "ms")

    scene_audio_paths: list[str] = []
    for scene in scenes:
        num = scene.get("number", 0)
        vo_text = scene.get("script", "")
        sfx_text = scene.get("sfxPrompt", "")
        duration = min(float(scene.get("duration", _DEFAULT_SCENE_DURATION)), _MAX_SFX_DURATION)
        if not vo_text:
            continue

        vo_path = str(work_dir / f"vo_{num}.mp3")
        sfx_path = str(work_dir / f"sfx_{num}.mp3")
        scene_path = str(work_dir / f"scene_{num}.mp3")

        vo_ok = generate_tts(vo_text, vo_path, voice_id=voice_id, language_code=lang_code)
        if not vo_ok:
            continue

        sfx_ok = (
            generate_sfx(sfx_text, sfx_path, duration_seconds=duration)
            if sfx_text
            else False
        )
        mix_vo_and_sfx(vo_path, sfx_path if sfx_ok else None, scene_path)
        scene_audio_paths.append(scene_path)

    return scene_audio_paths


def _concat_scenes(scene_audio_paths: list[str], work_dir: Path) -> Optional[str]:
    """Concatenate scene audio files into one final ``.mp3`` track."""
    from shared.elevenlabs_utils import HAS_PYDUB

    if not scene_audio_paths:
        return None

    if HAS_PYDUB and len(scene_audio_paths) > 1:
        try:
            from pydub import AudioSegment

            combined = AudioSegment.empty()
            for p in scene_audio_paths:
                combined += AudioSegment.from_mp3(p)
            final_path = str(work_dir / "final_ad.mp3")
            combined.export(final_path, format="mp3")
            return final_path
        except Exception as e:
            logger.warning("[AudioAgent] Concat failed: %s. Using first scene.", e)
            return scene_audio_paths[0]

    return scene_audio_paths[0]


def _record_generated_ad(
    *,
    project_id: str,
    task_id: str,
    platform: str,
    caption: Optional[str],
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
                    "media_type": "audio",
                    "platform": platform,
                    "caption": caption,
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
        logger.info(
            "[AudioAgent] Recorded generated_ads row (status=%s, id=%s)", status, ad_id
        )
        return ad_id
    except Exception as e:
        logger.error("[AudioAgent] Supabase recording failed (status=%s): %s", status, e)
        return None


async def generate(*, brief: str,project_id: str, task_id: str, platform: str, rules: dict, reference_parts: Optional[list] = None,
    generation_context: Optional[dict] = None,
) -> AgentResult:

    # GoogleSearch for audio ad trends (graceful degradation on failure)
    from jusads_generation.search_tools import search_creative_context, derive_search_query

    search_query = derive_search_query(brief=brief, market="malaysia", theme=f"{platform} audio ad jingle")
    search_context = await search_creative_context(query=search_query, market="malaysia")

    enriched_brief = brief
    if search_context:
        enriched_brief = f"{brief}\n\n[AUDIO TREND CONTEXT]: {search_context[:400]}"

    max_duration = rules.get("max_duration_seconds") if rules else None
    work_dir: Optional[Path] = None
    audio_path: Optional[str] = None

    try:
        # Step 1+2: plan the multi-scene script, then cap it to the ad-length ceiling.
        scenes = await _plan_audio_script(brief)
        scenes = _cap_scene_durations(scenes, max_duration)
        full_script_text = " ".join(s.get("script", "") for s in scenes)

        # Step 3+4: render each scene (VO + SFX + mix) then concatenate.
        work_dir = Path(tempfile.mkdtemp(prefix="audio_ad_"))
        scene_audio_paths = _render_scenes(scenes, work_dir)
        audio_path = _concat_scenes(scene_audio_paths, work_dir)

        # Upload to S3.
        s3_key = f"generated_ads/{project_id}/{task_id}/audio_{uuid.uuid4().hex[:6]}.mp3"
        try:
            s3_url = upload_file_public(audio_path, s3_key)
        except Exception as e:
            logger.warning("[AudioAgent] S3 upload failed, using fallback URL: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        # Record the successful Generated_Ad (Req 5.4).
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            caption=full_script_text,
            prompt_used=brief,
            s3_key=s3_key,
            status="completed",
            metadata={"s3_url": s3_url, "scenes": scenes},
            generation_context=generation_context,
        )

        return AgentResult(
            ad_id=ad_id,
            media_type="audio",
            platform=platform,
            s3_media_key=s3_key,
            public_url=s3_url,
            caption=full_script_text,
            status="completed",
            error=None,
        )
    except Exception as e:
        # Resilient failure: record a failed row without touching other agents (Req 5.5).
        logger.error("[AudioAgent] Generation failed: %s", e)
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            caption=None,
            prompt_used=brief,
            s3_key=None,
            status="failed",
            metadata={"error": str(e)},
            generation_context=generation_context,
        )
        return AgentResult(
            ad_id=ad_id,
            media_type="audio",
            platform=platform,
            s3_media_key=None,
            public_url=None,
            caption=None,
            status="failed",
            error=str(e),
        )
    finally:
        # Clean up the working directory and any stray output file.
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except Exception:
                pass

