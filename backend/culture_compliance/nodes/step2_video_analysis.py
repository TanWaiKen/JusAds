"""Step 2: Video processing node for the compliance pipeline.

Validates video format, size, and duration, then either:
- v3 path: If persona_narrative is set, sends video + compliance prompt
  directly to a single multimodal model (Pegasus/Claude) and produces
  the final compliance JSON in one step.
- v2 fallback: Sends video to Pegasus for a universal visual audit.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10
"""

import base64
import json
import logging
import os
import re
import subprocess
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from culture_compliance.config import AWS_REGION_LLM, CLAUDE_VIDEO_MODEL_ID, VIDEO_COMPLIANCE_MODEL, VIDEO_MODEL_ID
from culture_compliance.models.schemas import Market, PipelineState
from culture_compliance.scoring import get_scoring_config
from culture_compliance.services.video_model import analyze_video_for_compliance

logger = logging.getLogger(__name__)

# Constraints
MAX_VIDEO_SIZE_BYTES = 104_857_600  # 100 MB
MAX_DURATION_SECONDS = 300  # 5 minutes
MAX_BASE64_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB for Pegasus base64 input

# Supported video formats by extension
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".webm"}

# Magic bytes for video format detection
_MP4_FTYP_MARKER = b"ftyp"
_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"  # EBML header (Matroska/WebM)

# Boto3 client configuration
_bedrock_config = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    read_timeout=300,
)


def _get_bedrock_client():
    """Create a Bedrock Runtime client for Pegasus invocation."""
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION_LLM,
        config=_bedrock_config,
    )


def _merge_chronologically(
    frame_descriptions: list[dict], transcript_segments: list[dict]
) -> str:
    """Merge frame descriptions and transcript segments in chronological order.

    Args:
        frame_descriptions: List of dicts with 'timestamp' (float) and 'description' (str).
        transcript_segments: List of dicts with 'start_time' (float), 'end_time' (float), and 'text' (str).

    Returns:
        A newline-separated string with entries formatted as [MM:SS] [Visual|Audio] description,
        ordered by timestamp. Returns empty string if both inputs are empty.
    """
    if not frame_descriptions and not transcript_segments:
        return ""

    entries: list[tuple[float, str]] = []

    for frame in frame_descriptions:
        ts = frame.get("timestamp", 0.0)
        desc = frame.get("description", "")
        minutes = int(ts) // 60
        seconds = int(ts) % 60
        entries.append((ts, f"[{minutes:02d}:{seconds:02d}] [Visual] {desc}"))

    for segment in transcript_segments:
        ts = segment.get("start_time", 0.0)
        text = segment.get("text", "")
        minutes = int(ts) // 60
        seconds = int(ts) % 60
        entries.append((ts, f"[{minutes:02d}:{seconds:02d}] [Audio] {text}"))

    # Sort by timestamp (stable sort preserves insertion order for equal timestamps)
    entries.sort(key=lambda x: x[0])

    return "\n".join(entry[1] for entry in entries)


def _detect_video_format_by_extension(video_path: str) -> Optional[str]:
    ext = os.path.splitext(video_path)[1].lower()
    return ext if ext in SUPPORTED_EXTENSIONS else None


def _detect_video_format_by_magic(video_path: str) -> Optional[str]:
    try:
        with open(video_path, "rb") as f:
            header = f.read(32)
        if len(header) < 12:
            return None
        if header[4:8] == _MP4_FTYP_MARKER:
            brand = header[8:12]
            return ".mov" if brand in (b"qt  ", b"MSNV") else ".mp4"
        if header[:4] == _WEBM_MAGIC:
            return ".webm"
        return None
    except (OSError, IOError):
        return None


def _get_file_size(video_path: str) -> int:
    try:
        return os.path.getsize(video_path)
    except OSError:
        return 0


def _get_video_duration(video_path: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        duration_str = result.stdout.strip()
        if not duration_str:
            return None
        duration = float(duration_str)
        return duration if duration > 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def _analyze_video_with_pegasus(video_path: str, prompt: str) -> str:
    """Analyze a video using TwelveLabs Pegasus via Bedrock InvokeModel.

    Reads the video file, base64-encodes it, and sends to Pegasus for
    whole-video understanding in a single API call.

    Args:
        video_path: Path to the video file.
        prompt: The analysis prompt to send to Pegasus.

    Returns:
        The model's text response describing the video content.

    Raises:
        Exception: If the API call fails.
    """
    # Read and base64-encode the video
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    if len(video_bytes) > MAX_BASE64_SIZE_BYTES:
        raise ValueError(
            f"Video file too large for Pegasus base64 input "
            f"({len(video_bytes)} bytes, max {MAX_BASE64_SIZE_BYTES})"
        )

    video_b64 = base64.b64encode(video_bytes).decode("utf-8")

    # Build Pegasus request body
    request_body = {
        "inputPrompt": prompt,
        "mediaSource": {
            "base64String": video_b64,
        },
        "temperature": 0,
        "maxOutputTokens": 4096,
    }

    client = _get_bedrock_client()
    response = client.invoke_model(
        modelId=VIDEO_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    return response_body.get("message", "")


def video_processing(state: PipelineState) -> PipelineState:
    """Analyze video using TwelveLabs Pegasus for whole-video understanding.

    Performs the following steps:
    1. Validate video file exists
    2. Validate format (MP4/MOV/WebM)
    3. Validate size (≤100 MB) and duration (≤5 minutes)
    4. Send entire video to Pegasus for comprehensive analysis
    5. Set unified_content in state with the analysis result

    Args:
        state: The current pipeline state containing the submission.

    Returns:
        Updated PipelineState with unified_content set, or with errors
        appended if validation fails.
    """
    video_path = state.submission.content

    # Step 1: Validate the video file exists
    if not video_path or not video_path.strip():
        state.errors.append({
            "error_type": "validation",
            "message": "Video content path is empty",
            "details": {},
        })
        return state

    video_path = video_path.strip()

    if not os.path.exists(video_path):
        state.errors.append({
            "error_type": "validation",
            "message": f"Video file not found: {video_path}",
            "details": {"path": video_path},
        })
        return state

    # Step 2: Validate format
    fmt = _detect_video_format_by_extension(video_path)
    if fmt is None:
        fmt = _detect_video_format_by_magic(video_path)

    if fmt is None:
        state.errors.append({
            "error_type": "validation",
            "message": "Unsupported video format. Supported formats: MP4, MOV, WebM",
            "details": {"supported_formats": ["MP4", "MOV", "WebM"]},
        })
        return state

    # Step 3: Validate size
    file_size = _get_file_size(video_path)
    if file_size > MAX_VIDEO_SIZE_BYTES:
        state.errors.append({
            "error_type": "validation",
            "message": f"Video file exceeds maximum size of 100 MB. Received: {file_size} bytes",
            "details": {"max_size_bytes": MAX_VIDEO_SIZE_BYTES, "actual_size_bytes": file_size},
        })
        return state

    # Step 4: Validate duration
    duration = _get_video_duration(video_path)
    if duration is not None and duration > MAX_DURATION_SECONDS:
        state.errors.append({
            "error_type": "validation",
            "message": f"Video duration exceeds maximum of 5 minutes. Received: {duration:.1f} seconds",
            "details": {"max_duration_seconds": MAX_DURATION_SECONDS, "actual_duration_seconds": duration},
        })
        return state

    # Step 5: Choose v3 (persona-driven single-model) or v2 (universal audit) path
    if state.persona_narrative:
        # ── v3 Path: Single-model compliance evaluation ──
        return _video_compliance_v3(state, video_path, file_size)
    else:
        # ── v2 Fallback: Universal visual audit ──
        return _video_audit_v2(state, video_path, file_size)


def _video_audit_v2(state: PipelineState, video_path: str, file_size: int) -> PipelineState:
    """v2 path: Universal visual audit using Pegasus.

    Sends the video to Pegasus with a generic audit prompt. The text output
    is stored in unified_content for downstream evaluation by Nova-Pro (step6).
    """
    prompt = (
        "Analyze this video and provide a structured visual audit. Do not evaluate if the content is legal or illegal. "
        "You must output exactly two sections:\n\n"
        "1. NARRATIVE SUMMARY: A brief chronological summary of the video's events, spoken dialogue, and text overlays. Include precise timestamps (MM:SS) for every major action.\n"
        "2. VISUAL AUDIT TAGS: Scan the video and explicitly list if any of the following universal elements are visually present, no matter how briefly. For every element you find, you MUST include the exact timestamp (MM:SS) it appears on screen. If none are present, state 'None'.\n"
        "- Body Exposure (Specify exactly what skin/body parts are visible, e.g., bare armpits, midriff, thighs, uncovered hair, cleavage, and provide timestamps)\n"
        "- Physical Contact (Describe any touching between actors and provide timestamps)\n"
        "- Symbols & Attire (Religious symbols, traditional clothing, specific colors, and provide timestamps)\n"
        "- Food & Animals (Specify types of food, beverages, or animals shown, and provide timestamps)\n"
        "- Gestures & Text (Specific hand signs, numbers, or prominent text, and provide timestamps)"
    )

    logger.info("[v2] Analyzing video with Pegasus: %s (%.2f MB)", video_path, file_size / (1024 * 1024))

    try:
        analysis = _analyze_video_with_pegasus(video_path, prompt)
        state.models_used.append(VIDEO_MODEL_ID)
        logger.info("[v2] Pegasus analysis completed: %d characters", len(analysis))
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("Pegasus API error: %s - %s", error_code, str(e))
        state.errors.append({
            "error_type": "service_unavailable",
            "message": f"Video analysis model unavailable: {error_code}",
            "details": {"model": VIDEO_MODEL_ID},
        })
        return state
    except Exception as e:
        logger.error("Video analysis failed: %s", str(e))
        state.errors.append({
            "error_type": "service_unavailable",
            "message": f"Video analysis failed: {str(e)}",
            "details": {"model": VIDEO_MODEL_ID},
        })
        return state

    if not analysis:
        state.warnings.append({
            "step_name": "video_analysis",
            "description": "Pegasus returned empty analysis",
            "result_may_be_incomplete": True,
        })
        state.unified_content = "[Video] No analyzable content could be extracted."
    else:
        state.unified_content = analysis

    logger.info("[v2] Video processing completed: unified_length=%d", len(state.unified_content))
    return state


def _build_compliance_prompt(
    persona_narrative: str,
    regulatory_guidelines: str,
    market: str,
    ethnicity: str,
    age_group: str,
) -> str:
    """Build the single-model compliance evaluation prompt.

    Combines the persona narrative, regulatory guidelines, and scoring
    instructions into a prompt that asks the video model to directly
    output the compliance JSON.

    Args:
        persona_narrative: The cultural persona narrative text.
        regulatory_guidelines: Formatted regulatory guidelines string.
        market: Target market name.
        ethnicity: Target ethnicity.
        age_group: Target age group.

    Returns:
        The complete prompt string.
    """
    try:
        market_enum = Market(market.lower())
    except (ValueError, AttributeError):
        market_enum = Market.MALAYSIA

    scoring_config = get_scoring_config(market_enum)
    scoring_categories = "\n".join(
        f"- {cat.name}: weight {cat.weight}" for cat in scoring_config
    )
    market_name = market.title() if market else "Malaysia"

    return f"""\
You are a {market_name} Cultural Appropriateness Evaluator. Watch this video carefully and \
evaluate it from the perspective of the target viewer described below.

TARGET MARKET: {market_name}
TARGET ETHNICITY: {ethnicity.upper()}
TARGET AGE GROUP: {age_group.upper()}

TARGET VIEWER PERSONA:
{persona_narrative}

REGULATORY GUIDELINES:
{regulatory_guidelines or 'No regulatory guidelines available.'}

INSTRUCTIONS:
1. Watch the entire video carefully, noting exact timestamps (MM:SS) for every action.
2. Evaluate what you see against the TARGET VIEWER PERSONA and REGULATORY GUIDELINES.
3. If a visual element contradicts the persona's cultural expectations or regulatory rules, flag it as a violation with the EXACT timestamp.
4. Do not use outside knowledge. Base violations solely on the persona and guidelines provided.
5. Pay close attention to: body exposure, clothing modesty, physical contact, food/drink items, religious symbols, and product application scenes.

SCORING CATEGORIES AND WEIGHTS:
{scoring_categories}

SCORING METHOD:
Start from 100 points. For each category, apply severity penalties:
- No issues = 0 penalty
- Minor = 0.25 x weight
- Moderate = 0.6 x weight
- Severe = 1.0 x weight
SCORE = max(0, round(100 - total_penalty))

RISK LEVEL MAPPING:
- SCORE >= 75 -> "Low"
- 40 <= SCORE < 75 -> "Medium"
- SCORE < 40 -> "High"

For each violation, provide:
- "timestamp": exact "MM:SS" format when the violation appears on screen
- "description": what is happening at that moment (max 200 chars)
- "category": one of the scoring categories listed above
- "severity": one of "Severe", "Moderate", "Minor"
- "guideline_source": "regulatory" if it violates a regulatory guideline, "cultural" if it violates the persona's cultural expectations

OUTPUT FORMAT:
Produce ONLY a single JSON object (no extra text, no markdown fences) with these exact fields:
{{
  "risk_level": "High" | "Medium" | "Low",
  "score": integer 0-100,
  "high_risk_indicators": [array of up to 10 localized issue objects, ranked by severity (Severe first)],
  "explanation": "concise reasoning (max 500 characters)",
  "suggestion": "clear, actionable advice (max 400 characters)"
}}

RULES:
- Return ONLY valid JSON, no markdown code fences, no extra text.
- If no issues are found, return score 100, risk_level "Low", and empty high_risk_indicators array.
- Limit high_risk_indicators to maximum 10 items, ranked by severity.
- Every high_risk_indicator MUST have an accurate timestamp from the video.
"""


def _parse_llm_json(raw: str) -> Optional[dict]:
    """Parse LLM output as JSON, handling markdown code blocks."""
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _video_compliance_v3(state: PipelineState, video_path: str, file_size: int) -> PipelineState:
    """v3 path: Single-model persona-driven compliance evaluation.

    Sends the video + compliance prompt (with persona narrative and regulatory
    guidelines) directly to the configured video model (Pegasus or Claude).
    The model watches the video and outputs the final compliance JSON.
    """
    market_value = state.market.value if hasattr(state.market, "value") else str(state.market)

    # Trim regulatory guidelines for prompt — take only top 10 most relevant
    # to keep the prompt within model token limits.
    reg_guidelines = state.regulatory_guidelines or ""
    if reg_guidelines:
        guideline_entries = reg_guidelines.split("\n\n")
        if len(guideline_entries) > 10:
            reg_guidelines = "\n\n".join(guideline_entries[:10])
            logger.info("[v3] Trimmed regulatory guidelines from %d to 10 entries", len(guideline_entries))

    prompt = _build_compliance_prompt(
        persona_narrative=state.persona_narrative,
        regulatory_guidelines=reg_guidelines,
        market=market_value,
        ethnicity=state.target_ethnicity,
        age_group=state.target_age_group,
    )

    logger.info(
        "[v3] Prompt length: %d chars. Model: %s",
        len(prompt), VIDEO_COMPLIANCE_MODEL if VIDEO_COMPLIANCE_MODEL else "pegasus",
    )

    logger.info(
        "[v3] Single-model compliance evaluation: %s (%.2f MB)",
        video_path, file_size / (1024 * 1024),
    )

    try:
        raw_response = analyze_video_for_compliance(video_path, prompt)
        logger.info("[v3] Model response: %d characters", len(raw_response))
    except Exception as e:
        logger.error("[v3] Video compliance model failed: %s", str(e))
        state.errors.append({
            "error_type": "service_unavailable",
            "message": f"Video compliance model failed: {str(e)}",
            "details": {},
        })
        return state

    # Parse JSON response
    parsed = _parse_llm_json(raw_response)
    if parsed is None:
        logger.error("[v3] Failed to parse model response as JSON: %s", raw_response[:300])
        state.errors.append({
            "error_type": "parse_error",
            "message": "Video compliance model returned unparseable response.",
            "details": {"raw_preview": raw_response[:200]},
        })
        return state

    # Store results — same fields step6 would populate
    state.raw_llm_output = parsed
    state.unified_content = f"[Video compliance evaluated directly by video model]"

    # Track which model was used
    model_id = CLAUDE_VIDEO_MODEL_ID if VIDEO_COMPLIANCE_MODEL == "claude" else VIDEO_MODEL_ID
    if model_id not in state.models_used:
        state.models_used.append(model_id)

    logger.info(
        "[v3] Video compliance complete: risk_level=%s, score=%s",
        parsed.get("risk_level", "unknown"),
        parsed.get("score", "unknown"),
    )
    return state
