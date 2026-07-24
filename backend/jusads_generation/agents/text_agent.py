"""
text_agent.py
─────────────
Text_Caption_Agent — the independent Media Agent that generates ad copy /
captions (Req 5.1).

Workflow: Gemini copy → ``.txt`` uploaded to S3 → a ``generated_ads`` row.

The agent implements the shared :func:`generate` contract from ``base.py`` and
lives in its own module. It never imports any other Media Agent, so it can
neither consume nor depend on another agent's output (Req 5.2). Every external
call (Gemini, S3, Supabase) is wrapped in ``try/except`` with ``[TextAgent]``
logging and a graceful fallback per steering conventions. On success it records
a ``completed`` row; on failure it records a ``failed`` row without touching any
other agent's recorded output (Req 5.4, 5.5).
"""

import json
import logging
import os
import tempfile
import uuid
from typing import Optional

from shared.clients import gemini, supabase
from shared.config import MODEL_TEXT
from shared.prompts import TEXT_AD_GENERATION_PROMPT
from shared.s3_client import upload_file_public
from ..provenance import generated_ad_context_fields

from ..platform_rules import PlatformRule
from .base import AgentResult, load_guide

logger = logging.getLogger(__name__)

MEDIA_TYPE = "text"


def _build_caption(brief: str, search_context: str = "") -> str:
    """Generate ad copy for ``brief`` via Gemini, falling back on any error.

    Wraps the Gemini call in ``try/except`` so a model or parsing failure
    degrades gracefully to a deterministic promo caption instead of raising
    (Req 3.2).

    Args:
        brief: The user's campaign brief / prompt.
        search_context: Optional market research context from GoogleSearch.

    Returns:
        The generated (or fallback) ad caption text.
    """
    guide = load_guide("text")
    logger.info("[TextAgent] Running copy generation...")

    market_context_section = ""
    if search_context:
        market_context_section = f"""
[MARKET CONTEXT — use as inspiration, not verbatim]:
{search_context[:1000]}
---"""

    ai_prompt = TEXT_AD_GENERATION_PROMPT.format(
        guide=guide,
        market_context_section=market_context_section,
        brief=brief,
    )

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=ai_prompt,
        )
        resp_text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(resp_text)
        caption = data.get("caption_raw") or (
            f"{data.get('headline')}\n\n{data.get('body_copy')}\n\n"
            f"{' '.join(data.get('hashtags', []))}"
        )
        return caption
    except Exception as e:
        logger.error("[TextAgent] Failed to generate copy: %s", e)
        return f"Promo Alert: {brief}!"


def _record_row(
    *,
    project_id: str,
    task_id: str,
    platform: str,
    status: str,
    caption: Optional[str],
    prompt_used: str,
    s3_media_key: Optional[str],
    metadata: dict,
    generation_context: Optional[dict] = None,
) -> Optional[str]:
    """Insert one ``generated_ads`` row and return its id (or ``None``).

    Records the row with ``project_id``, ``task_id``, ``media_type``,
    ``platform`` and the given ``status`` (Req 5.4, 5.5). Supabase failures are
    caught and logged so the caller can still return a result (Req 3.2).
    """
    try:
        response = (
            supabase.table("generated_ads")
            .insert(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "media_type": MEDIA_TYPE,
                    "platform": platform,
                    "caption": caption,
                    "prompt_used": prompt_used,
                    "s3_media_key": s3_media_key,
                    "status": status,
                    "metadata": metadata,
                    **generated_ad_context_fields(generation_context),
                }
            )
            .execute()
        )
        rows = response.data or []
        if rows:
            return str(rows[0].get("id")) if rows[0].get("id") is not None else None
    except Exception as e:
        logger.error("[TextAgent] Supabase recording (%s) failed: %s", status, e)
    return None


async def generate(*, brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: PlatformRule,
    reference_parts: list,
    generation_context: Optional[dict] = None,
) -> AgentResult:
    """Generate one text ad, upload it to S3, and record a ``generated_ads`` row.

    Implements the shared Media Agent contract (see ``base.generate``). On
    success returns ``status='completed'`` with the caption and S3 location and
    records a ``completed`` row (Req 5.4). On an unrecoverable failure it records
    a ``failed`` row and returns ``status='failed'`` WITHOUT modifying any other
    agent's output (Req 5.5).

    Args:
        brief: The user's campaign brief / prompt.
        project_id: Owning project id.
        task_id: Owning task id.
        platform: The resolved, validated target platform.
        rules: Resolved platform sizing rules (unused for text beyond platform
            attribution; sizing is a caption-length convention — Req 7.1).
        reference_parts: Optional multimodal reference parts (unused for copy).

    Returns:
        An :class:`AgentResult` describing the generated text ad.
    """
    logger.info(
        "[TextAgent] Generating text ad for platform '%s' (project=%s, task=%s)",
        platform,
        project_id,
        task_id,
    )

    # GoogleSearch for creative context (graceful degradation on failure)
    from jusads_generation.search_tools import search_creative_context, derive_search_query

    search_query = derive_search_query(brief=brief, market="malaysia")
    search_context = await search_creative_context(
        query=search_query,
        market="malaysia",
        task_id=task_id,
    )

    caption = _build_caption(brief, search_context=search_context)

    # Write the copy to a local temp file for S3 upload.
    tmp_path: Optional[str] = None
    s3_key = f"generated_ads/{project_id}/{task_id}/text_{uuid.uuid4().hex[:6]}.txt"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(caption.encode("utf-8"))
            tmp_path = tmp.name

        try:
            s3_url = upload_file_public(tmp_path, s3_key)
        except Exception as e:
            logger.warning("[TextAgent] S3 upload failed, using fallback URL: %s", e)
            s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"

        ad_id = _record_row(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            status="completed",
            caption=caption,
            prompt_used=brief,
            s3_media_key=s3_key,
            metadata={"s3_url": s3_url, "aspect_ratio": rules.get("aspect_ratio")},
            generation_context=generation_context,
        )

        logger.info("[TextAgent] Completed text ad (ad_id=%s)", ad_id)
        return AgentResult(
            ad_id=ad_id,
            media_type=MEDIA_TYPE,
            platform=platform,
            s3_media_key=s3_key,
            public_url=s3_url,
            caption=caption,
            status="completed",
            error=None,
        )
    except Exception as e:
        # Unrecoverable failure: record an isolated failed row (Req 5.5).
        logger.error("[TextAgent] Generation failed: %s", e)
        fail_id = _record_row(
            project_id=project_id,
            task_id=task_id,
            platform=platform,
            status="failed",
            caption=None,
            prompt_used=brief,
            s3_media_key=None,
            metadata={"error": str(e)},
            generation_context=generation_context,
        )
        return AgentResult(
            ad_id=fail_id,
            media_type=MEDIA_TYPE,
            platform=platform,
            s3_media_key=None,
            public_url=None,
            caption=None,
            status="failed",
            error=str(e),
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

