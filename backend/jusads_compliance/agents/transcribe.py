"""
transcribe.py
─────────────
Agent: Transcribe audio/video media content using Gemini.

This agent only runs for audio and video media types (conditional edge).
Extracts spoken language and text transcript for downstream analysis.
"""

import logging
import mimetypes
from shared.models import Compliance_State
from shared.clients import gemini
from shared.config import MODEL_TEXT
from google.genai import types as genai_types
from jusads_compliance.progress_tracker import ProgressTracker
from jusads_compliance.utils import parse_json_res
from pydantic import BaseModel, Field
from typing import List

logger = logging.getLogger(__name__)
_tracker = ProgressTracker()
_MODEL = MODEL_TEXT


class TranscriptSegment(BaseModel):
    start_seconds: float = Field(description="Start timestamp of this spoken segment.")
    end_seconds: float = Field(description="End timestamp of this spoken segment.")
    text: str = Field(description="Verbatim transcript for this time range.")


class TranscribeSchema(BaseModel):
    transcript: str = Field(description="The complete spoken transcript of the media.")
    language: str = Field(description="The language code or name detected in the speech.")
    segments: List[TranscriptSegment] = Field(default_factory=list, description="Timestamped spoken segments.")


def transcribe_media(state: Compliance_State) -> dict:
    """Transcribe audio/video media content using Gemini.

    This node only runs for audio and video media types (conditional edge).
    """
    task_id = state["task_id"]
    step_name = "transcribe_media"
    _tracker.start_step(task_id, step_name)

    try:
        media_type = state["media_type"]
        input_path = state["input_path"]

        with open(input_path, "rb") as f:
            media_bytes = f.read()

        mime_type = mimetypes.guess_type(input_path)[0]
        if not mime_type:
            mime_type = "audio/mpeg" if media_type == "audio" else "video/mp4"

        # Use Gemini for transcription
        transcribe_prompt = (
            "Transcribe this media exactly. Return the detected language, full transcript, "
            "and ordered timestamped segments covering each spoken phrase."
        )

        response = gemini.models.generate_content(
            model=_MODEL,
            contents=[genai_types.Content(role="user", parts=[
                genai_types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
                genai_types.Part.from_text(text=transcribe_prompt),
            ])],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TranscribeSchema,
            ),
        )

        transcript_data = parse_json_res(response.text)
        transcript = transcript_data.get("transcript", "")
        language = transcript_data.get("language", "unknown")

        result = state.get("result", {}) or {}
        result["_transcript"] = {
            "language": language,
            "transcript": transcript,
            "segments": transcript_data.get("segments", []),
        }

        _tracker.complete_step(
            task_id, step_name,
            f"Transcribed {media_type}: language={language}, length={len(transcript)} chars",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[transcribe] Failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_transcript"] = {"language": "unknown", "transcript": "(transcription unavailable)"}
        return {"result": result}
