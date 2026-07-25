"""Generate localized, expressive ElevenLabs V3 audio advertisements."""

import json
import logging
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

from config import DEFAULT_VOICE
from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT
from shared.prompts import AUDIO_AD_GENERATION_PROMPT
from shared.s3_client import upload_file_public

from .base import AgentResult, load_guide
from ..provenance import generated_ad_context_fields

logger = logging.getLogger(__name__)

_DEFAULT_SCENE_DURATION = 5.0
_MIN_TOTAL_DURATION = 1.0
_MAX_SFX_DURATION = 22.0
_SUPPORTED_LANGUAGES = {"ms", "en", "zh", "ta"}
_ALLOWED_DELIVERY_TAGS = {
    "authoritative", "bright", "calm", "clear", "concerned", "confident",
    "energetic", "excited", "fast", "friendly", "playful", "softly",
    "urgent", "warmly",
}


def _resolve_audio_language(context: dict[str, Any]) -> str:
    """Resolve a spoken-copy language from the user's localization settings."""
    requested = str(context.get("language") or "auto").lower().strip()
    if requested in _SUPPORTED_LANGUAGES:
        return requested

    market = str(context.get("market") or "malaysia").lower()
    ethnicity = str(context.get("target_ethnicity") or "all").lower()
    if market == "singapore":
        return "en"
    return {"chinese": "zh", "indian": "ta", "malay": "ms"}.get(ethnicity, "ms")


def _clean_brief_for_fallback(brief: str) -> str:
    """Remove orchestration metadata before it can become spoken fallback copy."""
    clean = re.sub(r"\n?\[(?:SETTINGS|LOCALIZATION PLAN|AUDIO TREND CONTEXT).*?\]\n?", "\n", brief, flags=re.DOTALL)
    return clean.strip()[:300] or "Discover something made for your day. Try it now."


def _normalise_delivery_tags(value: object) -> list[str]:
    """Return up to three safe, model-useful ElevenLabs V3 delivery tags."""
    raw_tags = value if isinstance(value, list) else [value]
    tags: list[str] = []
    for raw_tag in raw_tags:
        if not isinstance(raw_tag, str):
            continue
        for candidate in raw_tag.split(","):
            tag = candidate.strip().strip("[]").lower()
            if tag in _ALLOWED_DELIVERY_TAGS and tag not in tags:
                tags.append(tag)
            if len(tags) == 3:
                return tags
    return tags


def _default_delivery_tags(index: int, total: int, creative_style: str, voice_tone: str) -> list[str]:
    """Choose intentionally different V3 performance direction for each scene role."""
    style = creative_style.lower().strip()
    tone = voice_tone.lower().strip()
    if index == 0:
        if style == "problem_punchline":
            return ["concerned", "urgent"]
        if style == "culture_anchor":
            return ["warmly", "friendly"]
        if style == "speaker_led":
            return ["confident", "clear"]
        if style == "product_hero":
            return ["softly", "clear"]
        return ["energetic", "fast"]
    if index == total - 1:
        return ["warmly", "confident"]
    if "authoritative" in tone or style == "speaker_led":
        return ["authoritative", "clear"]
    if "calm" in tone or "premium" in tone or style == "culture_anchor":
        return ["warmly", "clear"]
    if style == "problem_punchline":
        return ["bright", "excited"]
    return ["playful", "excited"]


def _normalise_audio_scenes(
    raw_scenes: object,
    fallback_script: str,
    creative_style: str,
    voice_tone: str,
) -> list[dict[str, Any]]:
    """Validate planner output and attach explicit delivery direction per scene."""
    candidates = raw_scenes if isinstance(raw_scenes, list) else []
    usable = [scene for scene in candidates if isinstance(scene, dict) and str(scene.get("script") or "").strip()]
    if not usable:
        usable = [{
            "number": 1,
            "duration": 8,
            "script": fallback_script,
            "sfxPrompt": "upbeat commercial background music",
        }]

    scenes: list[dict[str, Any]] = []
    for index, raw_scene in enumerate(usable):
        scene = dict(raw_scene)
        scene["number"] = index + 1
        scene["script"] = str(scene.get("script") or "").strip()
        scene["sfxPrompt"] = str(scene.get("sfxPrompt") or "").strip()
        tags = _normalise_delivery_tags(scene.get("deliveryTags"))
        if not tags:
            tags = _default_delivery_tags(index, len(usable), creative_style, voice_tone)
        scene["deliveryTags"] = tags
        scene["emotion"] = tags[0]
        scenes.append(scene)
    return scenes


async def _plan_audio_script(
    *,
    brief: str,
    market: str,
    target_ethnicity: str,
    age_group: str,
    language: str,
    creative_style: str,
    voice_tone: str,
    localization_plan: str,
) -> list[dict[str, Any]]:
    """Plan localized spoken copy and V3 direction without embedding settings in copy."""
    guide = load_guide("audio")
    planning_prompt = AUDIO_AD_GENERATION_PROMPT.format(
        guide=guide[:800],
        brief=brief,
        market=market,
        target_ethnicity=target_ethnicity,
        age_group=age_group,
        language=language,
        creative_style=creative_style,
        voice_tone=voice_tone,
        localization_plan=localization_plan or "Use natural, market-appropriate spoken language without stereotypes.",
    )

    try:
        response = gemini.models.generate_content(model=MODEL_TEXT, contents=planning_prompt)
        clean = (response.text or "").strip().replace("```json", "").replace("```", "")
        return _normalise_audio_scenes(
            json.loads(clean),
            _clean_brief_for_fallback(brief),
            creative_style,
            voice_tone,
        )
    except Exception as exc:
        logger.warning("[AudioAgent] Localized script planning failed: %s. Using fallback.", exc)
        return _normalise_audio_scenes([], _clean_brief_for_fallback(brief), creative_style, voice_tone)


def _cap_scene_durations(
    scenes: list[dict[str, Any]], max_duration_seconds: Optional[int]
) -> list[dict[str, Any]]:
    """Trim/scale scene durations so their total is within the platform ceiling."""
    if not scenes:
        return scenes

    normalized: list[dict[str, Any]] = []
    for scene in scenes:
        try:
            duration = float(scene.get("duration", _DEFAULT_SCENE_DURATION))
        except (TypeError, ValueError):
            duration = _DEFAULT_SCENE_DURATION
        capped = dict(scene)
        capped["duration"] = duration if duration > 0 else _DEFAULT_SCENE_DURATION
        normalized.append(capped)

    if not max_duration_seconds or max_duration_seconds <= 0:
        return normalized

    remaining = float(max_duration_seconds)
    result: list[dict[str, Any]] = []
    for scene in normalized:
        if remaining <= 0:
            break
        allotted = min(float(scene["duration"]), remaining)
        if allotted < _MIN_TOTAL_DURATION and result:
            break
        capped = dict(scene)
        capped["duration"] = allotted
        result.append(capped)
        remaining -= allotted

    if not result:
        first = dict(normalized[0])
        first["duration"] = max(_MIN_TOTAL_DURATION, float(max_duration_seconds))
        result = [first]

    logger.info(
        "[AudioAgent] Capped localized script to %.1fs across %d scene(s)",
        sum(float(scene["duration"]) for scene in result),
        len(result),
    )
    return result


def _build_planned_script(scenes: list[dict[str, Any]]) -> str:
    """Build the exact scene-level V3-directed script shown on the Audio Agent node."""
    from shared.elevenlabs_utils import format_v3_delivery_text

    lines: list[str] = []
    for scene in scenes:
        script = str(scene.get("script") or "").strip()
        if not script:
            continue
        tts_script = format_v3_delivery_text(script, scene.get("deliveryTags"))
        scene["ttsScript"] = tts_script
        lines.append(f"Scene {scene.get('number', len(lines) + 1)} · {float(scene.get('duration', _DEFAULT_SCENE_DURATION)):g}s\n{tts_script}")
    return "\n\n".join(lines)


def _render_scenes(
    scenes: list[dict[str, Any]],
    work_dir: Path,
    language_code: str,
    speed: float = 1.0,
) -> list[str]:
    """Render deliberate scene-specific V3 delivery, retaining fallback-only multilingual v2."""
    from shared.elevenlabs_utils import generate_sfx, generate_tts, mix_vo_and_sfx

    voice_id = DEFAULT_VOICE["voice_id"]
    scene_audio_paths: list[str] = []
    for scene in scenes:
        num = int(scene.get("number", 0))
        vo_text = str(scene.get("script") or "").strip()
        sfx_text = str(scene.get("sfxPrompt") or "").strip()
        delivery_tags = _normalise_delivery_tags(scene.get("deliveryTags"))
        duration = min(float(scene.get("duration", _DEFAULT_SCENE_DURATION)), _MAX_SFX_DURATION)
        if not vo_text:
            continue

        vo_path = str(work_dir / f"vo_{num}.mp3")
        sfx_path = str(work_dir / f"sfx_{num}.mp3")
        scene_path = str(work_dir / f"scene_{num}.mp3")
        vo_ok = generate_tts(
            text=vo_text,
            output_path=vo_path,
            voice_id=voice_id,
            model_id="eleven_v3",
            language_code=language_code,
            delivery_tags=delivery_tags,
            speed=speed,
        )
        if not vo_ok:
            continue

        sfx_ok = generate_sfx(sfx_text, sfx_path, duration_seconds=duration) if sfx_text else False
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
            for path in scene_audio_paths:
                combined += AudioSegment.from_mp3(path)
            final_path = str(work_dir / "final_ad.mp3")
            combined.export(final_path, format="mp3")
            return final_path
        except Exception as exc:
            logger.warning("[AudioAgent] Concat failed: %s. Using first scene.", exc)
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
    metadata: dict[str, Any],
    generation_context: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Insert a generated-audio row and return its id on a best-effort basis."""
    try:
        response = supabase.table("generated_ads").insert({
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
        }).execute()
        rows = response.data or []
        ad_id = rows[0].get("id") if rows else None
        logger.info("[AudioAgent] Recorded generated_ads row (status=%s, id=%s)", status, ad_id)
        return ad_id
    except Exception as exc:
        logger.error("[AudioAgent] Supabase recording failed (status=%s): %s", status, exc)
        return None


async def generate(
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: dict,
    reference_parts: Optional[list] = None,
    generation_context: Optional[dict] = None,
) -> AgentResult:
    """Generate a localized, scene-directed audio ad and return its downloadable MP3."""
    from jusads_generation.search_tools import derive_search_query, search_creative_context

    context = generation_context or {}
    market = str(context.get("market") or "malaysia").lower()
    ethnicity = str(context.get("target_ethnicity") or "all").lower()
    age_group = str(context.get("age_group") or "all_ages").lower()
    language = _resolve_audio_language(context)
    creative_style = str(context.get("creative_style") or "meme_shock").lower()
    voice_tone = str(
        context.get("preferred_delivery")
        or context.get("voice_tone")
        or context.get("brand_tone")
        or "energetic"
    )
    localization_plan = str(context.get("localization_plan") or "")
    raw_brief = _clean_brief_for_fallback(brief)
    work_dir: Optional[Path] = None
    audio_path: Optional[str] = None

    try:
        search_query = derive_search_query(
            brief=raw_brief,
            market=market,
            theme=f"{platform} {language} audio ad jingle",
        )
        search_context = await search_creative_context(query=search_query, market=market)
        planning_brief = raw_brief
        if search_context:
            planning_brief = f"{raw_brief}\n\n[AUDIO TREND CONTEXT]: {search_context[:400]}"

        scenes = await _plan_audio_script(
            brief=planning_brief,
            market=market,
            target_ethnicity=ethnicity,
            age_group=age_group,
            language=language,
            creative_style=creative_style,
            voice_tone=voice_tone,
            localization_plan=localization_plan,
        )
        scenes = _cap_scene_durations(scenes, (rules or {}).get("max_duration_seconds"))
        planned_script = _build_planned_script(scenes)
        full_script_text = " ".join(str(scene.get("script") or "").strip() for scene in scenes).strip()

        work_dir = Path(tempfile.mkdtemp(prefix="audio_ad_"))
        target_speed = float(context.get("speed") or (rules or {}).get("speed") or 1.0)
        scene_audio_paths = _render_scenes(scenes, work_dir, language_code=language, speed=target_speed)
        audio_path = _concat_scenes(scene_audio_paths, work_dir)
        if not audio_path or not Path(audio_path).is_file():
            raise RuntimeError("Audio scene rendering produced no playable output")

        s3_key = f"generated_ads/{project_id}/{task_id}/audio_{uuid.uuid4().hex[:6]}.mp3"
        try:
            s3_url = upload_file_public(audio_path, s3_key)
        except Exception as exc:
            logger.warning("[AudioAgent] S3 upload failed, using fallback URL: %s", exc)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        metadata = {
            "s3_url": s3_url,
            "scenes": scenes,
            "planned_script": planned_script,
            "tts_model_requested": "eleven_v3",
            "market": market,
            "target_ethnicity": ethnicity,
            "language": language,
            "creative_style": creative_style,
        }
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            caption=full_script_text,
            prompt_used=raw_brief,
            s3_key=s3_key,
            status="completed",
            metadata=metadata,
            generation_context=context,
        )
        return {
            "ad_id": ad_id,
            "media_type": "audio",
            "platform": platform,
            "s3_media_key": s3_key,
            "public_url": s3_url,
            "caption": full_script_text,
            "planned_script": planned_script,
            "status": "completed",
            "error": None,
        }
    except Exception as exc:
        logger.error("[AudioAgent] Generation failed: %s", exc)
        ad_id = _record_generated_ad(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            caption=None,
            prompt_used=raw_brief,
            s3_key=None,
            status="failed",
            metadata={"error": str(exc)},
            generation_context=context,
        )
        return {
            "ad_id": ad_id,
            "media_type": "audio",
            "platform": platform,
            "s3_media_key": None,
            "public_url": None,
            "caption": None,
            "planned_script": None,
            "status": "failed",
            "error": str(exc),
        }
    finally:
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except OSError:
                pass

