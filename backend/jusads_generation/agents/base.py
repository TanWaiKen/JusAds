"""
base.py
───────
Shared contract and pure helpers for the four independent Media Agents
(Text Caption, Image, Audio, Video).

This module holds only the shared agent result type, the ``generate(...)``
contract signature, and pure helpers migrated faithfully from the legacy
``agent/generation_agent.py`` (``load_multimodal_reference``, ``NODE_COORDS``).
It contains no per-agent implementation and no orchestration, routing, or
persistence logic (Req 1.1).
"""

import logging
import mimetypes
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, TypedDict

from jusads_generation.state import MediaType

logger = logging.getLogger(__name__)

# Coordinates mapping for canvas node placements (migrated from generation_agent.py).
NODE_COORDS: dict[str, tuple[int, int]] = {
    "orchestrator": (100, 150),
    "text": (300, 50),
    "image": (300, 250),
    "audio": (500, 50),
    "video": (500, 250),
    "critic": (700, 150),
    "input": (50, 150),
    "output": (900, 150),
}


class AgentResult(TypedDict):
    """The result returned by every Media Agent's ``generate(...)`` call."""

    ad_id: Optional[str]
    media_type: MediaType
    platform: str
    s3_media_key: Optional[str]
    public_url: Optional[str]
    caption: Optional[str]
    status: str  # 'completed' | 'failed'
    error: Optional[str]


def load_guide(media_type: str) -> str:
    """Return a stable fallback after removal of obsolete agent guide files."""
    return f"Follow the campaign brief, platform rules, and runtime prompt for {media_type} ad generation."


async def load_multimodal_reference(url: str) -> Optional[dict]:
    """Download reference URL locally and wrap as a GenAI Part."""
    from google.genai import types as genai_types

    try:
        suffix = Path(url).suffix or ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()

        logger.info("[Orchestrator] Downloading reference asset: %s", url)
        urllib.request.urlretrieve(url, tmp.name)

        with open(tmp.name, "rb") as f:
            data = f.read()

        mime_type, _ = mimetypes.guess_type(tmp.name)
        if not mime_type:
            mime_type = "image/png"

        try:
            os.unlink(tmp.name)
        except Exception:
            pass

        return genai_types.Part.from_bytes(data=data, mime_type=mime_type)
    except Exception as e:
        logger.error("[Orchestrator] Failed to load reference URL %s: %s", url, e)
        return None


async def generate(
    *,
    brief: str,
    project_id: str,
    task_id: str,
    platform: str,
    rules: dict,
    reference_parts: Optional[list] = None,
) -> AgentResult:
    """Media Agent generation contract.

    Generate one output, upload it to S3, insert a ``generated_ads`` row
    (Req 5.4), and return an :class:`AgentResult`. On failure, record a
    ``'failed'`` row (Req 5.5) and return ``status='failed'`` WITHOUT touching
    any other agent's output.

    This module defines only the contract signature. Each Media Agent
    (``text_agent``, ``image_agent``, ``audio_agent``, ``video_agent``)
    implements its own concrete ``generate`` following this shape.
    """
    raise NotImplementedError(
        "generate(...) is the shared Media Agent contract; implement it in each "
        "concrete agent module (text_agent, image_agent, audio_agent, video_agent)."
    )
