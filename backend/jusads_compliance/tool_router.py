"""
tool_router.py
──────────────
Intelligent Remediation Engine — AI Tool Router (Phase R1).

Uses Gemini to classify the severity of compliance violations and pick
the cheapest/fastest editing tool that can handle the fix.

Decision matrix:
  - MINOR edits → CapCut (video), Inpaint (image), Dub segment (audio), Rewrite phrase (text)
  - MODERATE edits → CapCut scene replace (video), Imagen constrained (image), Voice clone full re-read (audio), Full rewrite (text)
  - MAJOR redo → Veo re-generate (video), Imagen full regen (image), New VO from scratch (audio), Complete new copy (text)

The AI decides — the user does NOT manually pick the tool.
"""

import json
import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Enumerations & Models
# -----------------------------------------------------------------------------

class Severity(str, Enum):
    """Severity level for a remediation action."""
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


class RemediationTool(str, Enum):
    """Available remediation tools in the system."""
    # Video tools
    CAPCUT_TEXT_OVERLAY = "capcut_text_overlay"
    CAPCUT_TRIM = "capcut_trim"
    CAPCUT_SPEED_RAMP = "capcut_speed_ramp"
    CAPCUT_SCENE_REPLACE = "capcut_scene_replace"
    CAPCUT_TRANSITION = "capcut_transition"
    OMNI_VIDEO_EDIT = "omni_video_edit"
    VEO_REGENERATE = "veo_regenerate"

    # Image tools
    INPAINT_AREA = "inpaint_area"
    EDIT_IMAGE = "edit_image"
    EDIT_IMAGE_REPLACE = "edit_image_replace"
    RECONTEXT_IMAGE = "recontext_image"
    RECONTEXT_BACKGROUND = "recontext_background"
    IMAGEN_CONSTRAINED = "imagen_constrained"
    IMAGEN_FULL_REGEN = "imagen_full_regen"
    UPSCALE_IMAGE = "upscale_image"

    # Audio tools
    ELEVENLABS_DUB_SEGMENT = "elevenlabs_dub_segment"
    ELEVENLABS_VOICE_CLONE_REREAD = "elevenlabs_voice_clone_reread"
    ELEVENLABS_NEW_VO = "elevenlabs_new_vo"
    ELEVENLABS_SFX_REPLACE = "elevenlabs_sfx_replace"

    # Text tools
    GEMINI_REWRITE_PHRASE = "gemini_rewrite_phrase"
    GEMINI_FULL_REWRITE = "gemini_full_rewrite"
    GEMINI_NEW_COPY = "gemini_new_copy"


class ToolSelection(BaseModel):
    """A single tool selection from the AI router."""
    tool: str = Field(description="The remediation tool to use")
    severity: str = Field(description="minor, moderate, or major")
    reasoning: str = Field(description="Why this tool was chosen")
    target_description: str = Field(description="What specifically needs fixing")
    estimated_cost: str = Field(description="low, medium, or high")
    estimated_time_seconds: int = Field(description="Rough time estimate in seconds")


class RoutingDecision(BaseModel):
    """Complete routing decision from the AI Tool Router."""
    media_type: str
    overall_severity: str = Field(description="minor, moderate, or major")
    tools: list[ToolSelection] = Field(description="Ordered list of tools to apply")
    strategy_summary: str = Field(description="One-line summary of the remediation plan")
    preserves_original: bool = Field(default=True, description="Whether original is kept intact")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Router confidence 0-1")


# -----------------------------------------------------------------------------
# Tool cost/speed metadata (used for fallback routing)
# -----------------------------------------------------------------------------

TOOL_METADATA: dict[str, dict] = {
    # Video
    "capcut_text_overlay": {"cost": "low", "time_s": 5, "severity_max": "minor"},
    "capcut_trim": {"cost": "low", "time_s": 10, "severity_max": "minor"},
    "capcut_speed_ramp": {"cost": "low", "time_s": 5, "severity_max": "minor"},
    "capcut_scene_replace": {"cost": "medium", "time_s": 30, "severity_max": "moderate"},
    "capcut_transition": {"cost": "low", "time_s": 5, "severity_max": "minor"},
    "omni_video_edit": {"cost": "medium", "time_s": 40, "severity_max": "moderate"},
    "veo_regenerate": {"cost": "high", "time_s": 120, "severity_max": "major"},
    # Image
    "inpaint_area": {"cost": "low", "time_s": 15, "severity_max": "minor"},
    "edit_image": {"cost": "low", "time_s": 20, "severity_max": "minor"},
    "edit_image_replace": {"cost": "low", "time_s": 20, "severity_max": "minor"},
    "recontext_image": {"cost": "low", "time_s": 15, "severity_max": "minor"},
    "recontext_background": {"cost": "low", "time_s": 15, "severity_max": "minor"},
    "upscale_image": {"cost": "low", "time_s": 10, "severity_max": "minor"},
    "imagen_constrained": {"cost": "medium", "time_s": 30, "severity_max": "moderate"},
    "imagen_full_regen": {"cost": "high", "time_s": 45, "severity_max": "major"},
    # Audio
    "elevenlabs_dub_segment": {"cost": "low", "time_s": 10, "severity_max": "minor"},
    "elevenlabs_voice_clone_reread": {"cost": "medium", "time_s": 30, "severity_max": "moderate"},
    "elevenlabs_new_vo": {"cost": "medium", "time_s": 20, "severity_max": "major"},
    "elevenlabs_sfx_replace": {"cost": "low", "time_s": 8, "severity_max": "minor"},
    # Text
    "gemini_rewrite_phrase": {"cost": "low", "time_s": 3, "severity_max": "minor"},
    "gemini_full_rewrite": {"cost": "low", "time_s": 5, "severity_max": "moderate"},
    "gemini_new_copy": {"cost": "low", "time_s": 8, "severity_max": "major"},
}

# Maps media_type -> severity -> preferred tools (ordered by preference)
TOOL_PRIORITY: dict[str, dict[str, list[str]]] = {
    "video": {
        "minor": ["capcut_text_overlay", "capcut_trim", "capcut_speed_ramp", "capcut_transition"],
        "moderate": ["omni_video_edit", "capcut_scene_replace", "capcut_trim"],
        "major": ["omni_video_edit", "veo_regenerate"],
    },
    "image": {
        "minor": ["inpaint_area", "edit_image", "recontext_image", "edit_image_replace", "recontext_background", "upscale_image"],
        "moderate": ["imagen_constrained"],
        "major": ["imagen_full_regen"],
    },
    "audio": {
        "minor": ["elevenlabs_dub_segment", "elevenlabs_sfx_replace"],
        "moderate": ["elevenlabs_voice_clone_reread"],
        "major": ["elevenlabs_new_vo"],
    },
    "text": {
        "minor": ["gemini_rewrite_phrase"],
        "moderate": ["gemini_full_rewrite"],
        "major": ["gemini_new_copy"],
    },
}


# -----------------------------------------------------------------------------
# AI-powered routing (Gemini)
# -----------------------------------------------------------------------------

_ROUTER_PROMPT = """You are an AI Tool Router for an advertising compliance remediation system.

Given a compliance violation report, classify the severity and select the CHEAPEST + FASTEST tool(s) that can fix the issues.

## Media Type: {media_type}

## Available Tools for {media_type}:
{available_tools}

## Severity Definitions:
- MINOR: Small localized fix (typo, one word, small image region, subtitle text, single audio word/phrase)
- MODERATE: Significant change but structure preserved (scene rework, tone shift, image region >30%, full voiceover re-read)
- MAJOR: Complete redo needed (fundamentally non-compliant concept, banned product shown prominently)

## Decision Rules:
1. ALWAYS prefer the cheapest tool that can handle the job
2. Minor issues NEVER escalate to major tools (no Veo for a subtitle fix)
3. Multiple minor tools can combine (e.g., trim + text overlay)
4. MAJOR is last resort — only when the content concept itself is the violation
5. For audio: if only 1-2 words need changing → dub_segment. If tone/accent wrong → voice_clone_reread. If content is fundamentally wrong → new_vo.
6. For video: if subtitle/CTA wrong → text_overlay. If a segment is non-compliant → trim or scene_replace. If you need to edit elements/characters/objects in the video while preserving motion → omni_video_edit. If entire video concept is wrong → veo_regenerate.

## Compliance Violations:
{violations_json}

## Additional Context:
- Risk Level: {risk_level}
- Risk Percentage: {risk_percentage}%
- Suggestion from compliance: {suggestion}
- Localization guidance: {localization_plan}

## Response Format (JSON):
{{
  "overall_severity": "minor|moderate|major",
  "tools": [
    {{
      "tool": "<tool_name>",
      "severity": "minor|moderate|major",
      "reasoning": "<why this tool>",
      "target_description": "<what to fix>",
      "estimated_cost": "low|medium|high",
      "estimated_time_seconds": <int>
    }}
  ],
  "strategy_summary": "<one line describing the plan>",
  "confidence": <0.0-1.0>
}}

Return ONLY valid JSON. Pick the minimal set of tools needed."""


def _build_tools_description(media_type: str) -> str:
    """Build a formatted description of available tools for a media type."""
    tools_for_type = TOOL_PRIORITY.get(media_type, {})
    lines = []
    for severity, tool_names in tools_for_type.items():
        for name in tool_names:
            meta = TOOL_METADATA.get(name, {})
            lines.append(
                f"- {name} (severity: {severity}, cost: {meta.get('cost', '?')}, "
                f"time: ~{meta.get('time_s', '?')}s)"
            )
    return "\n".join(lines)


async def route_remediation(
    media_type: str,
    violations: list[str],
    risk_level: str,
    risk_percentage: int,
    suggestion: str = "",
    localization_plan: str = "",
    violations_timeline: Optional[list[dict]] = None,
) -> RoutingDecision:
    """Use Gemini to classify severity and pick remediation tools.

    Falls back to heuristic routing if Gemini is unavailable or returns
    an unparseable response.

    Args:
        media_type: One of "video", "image", "audio", "text".
        violations: List of high-risk indicator strings from compliance.
        risk_level: Risk level string ("Low", "Moderate", "High", "Critical").
        risk_percentage: Integer 0-100.
        suggestion: Compliance suggestion text.
        localization_plan: Localization guidance text.
        violations_timeline: Optional list of violation segments with timestamps.

    Returns:
        RoutingDecision with selected tools and strategy.
    """
    from shared.clients import gemini as gemini_client
    from shared.config import MODEL_TEXT

    if not gemini_client:
        logger.warning("[ToolRouter] Gemini unavailable — falling back to heuristic routing")
        return _heuristic_route(media_type, violations, risk_level, risk_percentage)

    # Build violations context
    violations_context = {
        "high_risk_indicators": violations,
        "risk_level": risk_level,
        "risk_percentage": risk_percentage,
    }
    if violations_timeline:
        violations_context["timeline"] = violations_timeline[:5]  # Limit for prompt size

    prompt = _ROUTER_PROMPT.format(
        media_type=media_type,
        available_tools=_build_tools_description(media_type),
        violations_json=json.dumps(violations_context, indent=2),
        risk_level=risk_level,
        risk_percentage=risk_percentage,
        suggestion=suggestion[:500],
        localization_plan=localization_plan[:300],
    )

    try:
        from google.genai import types as genai_types

        response = gemini_client.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,  # Low temp for deterministic routing
            ),
        )

        result = json.loads(response.text)

        # Validate and build RoutingDecision
        tools = []
        for t in result.get("tools", []):
            # Validate tool name exists
            tool_name = t.get("tool", "")
            if tool_name not in TOOL_METADATA:
                logger.warning("[ToolRouter] Unknown tool from Gemini: %s — skipping", tool_name)
                continue
            tools.append(ToolSelection(
                tool=tool_name,
                severity=t.get("severity", "minor"),
                reasoning=t.get("reasoning", ""),
                target_description=t.get("target_description", ""),
                estimated_cost=t.get("estimated_cost", TOOL_METADATA[tool_name]["cost"]),
                estimated_time_seconds=t.get("estimated_time_seconds", TOOL_METADATA[tool_name]["time_s"]),
            ))

        if not tools:
            logger.warning("[ToolRouter] Gemini returned no valid tools — falling back to heuristic")
            return _heuristic_route(media_type, violations, risk_level, risk_percentage)

        overall_severity = result.get("overall_severity", "minor")
        if overall_severity not in ("minor", "moderate", "major"):
            overall_severity = "minor"

        decision = RoutingDecision(
            media_type=media_type,
            overall_severity=overall_severity,
            tools=tools,
            strategy_summary=result.get("strategy_summary", f"Apply {len(tools)} tool(s) to fix violations"),
            preserves_original=True,
            confidence=min(1.0, max(0.0, result.get("confidence", 0.8))),
        )

        logger.info(
            "[ToolRouter] Gemini decision: severity=%s, tools=%s, confidence=%.2f",
            decision.overall_severity,
            [t.tool for t in decision.tools],
            decision.confidence,
        )
        return decision

    except Exception as e:
        logger.error("[ToolRouter] Gemini routing failed: %s — falling back to heuristic", e)
        return _heuristic_route(media_type, violations, risk_level, risk_percentage)


# -----------------------------------------------------------------------------
# Heuristic fallback (no AI call)
# -----------------------------------------------------------------------------


def _heuristic_route(
    media_type: str,
    violations: list[str],
    risk_level: str,
    risk_percentage: int,
) -> RoutingDecision:
    """Deterministic fallback routing when Gemini is unavailable.

    Uses risk_percentage thresholds:
      - ≤ 40% → MINOR
      - 41-70% → MODERATE
      - > 70% → MAJOR
    """
    # Determine severity from risk percentage
    if risk_percentage <= 40:
        severity = "minor"
    elif risk_percentage <= 70:
        severity = "moderate"
    else:
        severity = "major"

    # Get the preferred tools for this media_type + severity
    tools_for_type = TOOL_PRIORITY.get(media_type, {})
    tool_names = tools_for_type.get(severity, [])

    if not tool_names:
        # Fallback: pick the first available tool for any severity
        for sev in ("minor", "moderate", "major"):
            tool_names = tools_for_type.get(sev, [])
            if tool_names:
                severity = sev
                break

    tools = []
    for name in tool_names[:2]:  # Max 2 tools in heuristic mode
        meta = TOOL_METADATA.get(name, {})
        tools.append(ToolSelection(
            tool=name,
            severity=severity,
            reasoning=f"Heuristic fallback: risk_percentage={risk_percentage}% maps to {severity}",
            target_description="; ".join(violations[:3]) if violations else "Fix compliance issues",
            estimated_cost=meta.get("cost", "medium"),
            estimated_time_seconds=meta.get("time_s", 30),
        ))

    return RoutingDecision(
        media_type=media_type,
        overall_severity=severity,
        tools=tools,
        strategy_summary=f"Heuristic: {severity} fix using {', '.join(t.tool for t in tools)}",
        preserves_original=True,
        confidence=0.5,  # Lower confidence for heuristic
    )


# -----------------------------------------------------------------------------
# Convenience: synchronous wrapper for non-async contexts
# -----------------------------------------------------------------------------


def route_remediation_sync(
    media_type: str,
    violations: list[str],
    risk_level: str,
    risk_percentage: int,
    suggestion: str = "",
    localization_plan: str = "",
    violations_timeline: Optional[list[dict]] = None,
) -> RoutingDecision:
    """Synchronous version of route_remediation for use in LangGraph nodes.

    Falls back to heuristic if event loop issues arise.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — use heuristic to avoid nested loop issues
            # The async version should be called directly in async contexts
            logger.info("[ToolRouter] Running in async context — using heuristic fallback")
            return _heuristic_route(media_type, violations, risk_level, risk_percentage)
        return loop.run_until_complete(
            route_remediation(
                media_type, violations, risk_level, risk_percentage,
                suggestion, localization_plan, violations_timeline,
            )
        )
    except RuntimeError:
        # No event loop — create one
        return asyncio.run(
            route_remediation(
                media_type, violations, risk_level, risk_percentage,
                suggestion, localization_plan, violations_timeline,
            )
        )
