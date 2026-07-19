"""Evidence-gathering agent for regulatory compliance checks.

Google Search grounding is preferred when the configured Gemini client supports
it. Tavily is the audited fallback, so every final compliance decision has a
source trail instead of a separate hallucination score.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.genai import types as genai_types

from jusads_compliance.progress_tracker import ProgressTracker
from jusads_compliance.rules_client import get_persona, get_rules
from jusads_compliance.utils import parse_json_res
from shared.clients import gemini
from shared.config import MODEL_TEXT
from shared.models import Compliance_State
from shared.tavily_guard import tavily_compliance_research

logger = logging.getLogger(__name__)
_tracker = ProgressTracker()


def build_generation_localization_plan(
    *, brief: str, market: str, platform: str, ethnicity: str, age_group: str, language: str, task_id: str
) -> dict[str, Any]:
    """Create a source-backed localisation plan before a creative is generated.

    There is no media asset to assess yet, so this reuses the compliance
    research providers with the campaign brief as the research subject.  It is
    intentionally guidance rather than an approval verdict.
    """
    market_name = market.replace("_", " ")
    platform_name = platform.replace("_", " ")
    queries = [
        f"{market_name} {platform_name} advertising policy official claims certification language",
        f"{market_name} advertising regulations for {brief[:180]} official guidance",
    ]
    reports: list[str] = []
    sources: list[dict[str, str]] = []
    provider = "none"
    for query in queries:
        research = _google_grounded_research(query)
        if research:
            provider = "google_grounding"
        else:
            research = tavily_compliance_research(query=query, task_id=task_id) or {}
            if research:
                provider = "tavily"
        reports.append(research.get("content", ""))
        sources.extend(research.get("sources", []))

    deduped_sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in sources:
        url = source.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduped_sources.append(source)

    rules = get_rules(market=market, platform=platform) or []
    persona = get_persona(market=market, ethnicity=ethnicity, age_group=age_group) or {}
    language_note = language if language and language != "auto" else "No user language preference supplied"
    prompt = f"""Create a concise, source-backed PRE-GENERATION localisation plan for an advertisement.
It must guide a creative team, not decide whether an unseen ad is compliant.

CAMPAIGN BRIEF: {brief}
MARKET: {market}
PLATFORM: {platform}
AUDIENCE: {ethnicity}, {age_group}
USER LANGUAGE PREFERENCE: {language_note}
LOCAL RULES: {json.dumps(rules, ensure_ascii=False)}
PERSONA: {json.dumps(persona, ensure_ascii=False)}
RESEARCH: {' '.join(reports)}

Return plain text with four labelled short sections:
COPY & LANGUAGE (respect user preference; use copy-safe space, no text rendered in image),
PEOPLE & CONTEXT (role/attire/conduct/age, never assumed ethnicity or religion),
CLAIMS & CERTIFICATION (do not create badges or claims without proof), and
SENSITIVE CONTENT (avoid graphic violence, conflict-promotion, extremist or hate material).
Only describe a legal or platform requirement when the supplied rules/research supports it. Otherwise mark it as optional market guidance or evidence required."""
    try:
        response = gemini.models.generate_content(model=MODEL_TEXT, contents=prompt)
        plan = (response.text or "").strip()
    except Exception as exc:
        logger.warning("[ResearchAgent] Generation localisation synthesis failed: %s", exc)
        plan = ""

    return {
        "localization_plan": plan,
        "sources": deduped_sources[:10],
        "provider": provider,
    }


def _queries(state: Compliance_State, result: dict) -> list[str]:
    market = state["market"].replace("_", " ")
    platform = state["platform"].replace("_", " ")
    indicators = result.get("high_risk_indicator", [])[:3]
    if not indicators:
        return [f"{market} {platform} advertising regulations official guidance"]
    return [
        f"{market} {platform} advertising regulation {indicator} official"
        for indicator in indicators
    ]


def _google_grounded_research(query: str) -> dict[str, Any]:
    """Use Gemini Google Search grounding when supported by this deployment."""
    if gemini is None or not hasattr(genai_types, "GoogleSearch"):
        return {}
    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=(
                "Research this advertising-compliance question. Prefer primary "
                "regulator or platform sources. State only source-supported facts.\n\n"
                f"QUESTION: {query}"
            ),
            config=genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            ),
        )
        metadata = getattr(response.candidates[0], "grounding_metadata", None) if response.candidates else None
        sources: list[dict[str, str]] = []
        for chunk in getattr(metadata, "grounding_chunks", []) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None)
            if uri:
                sources.append({
                    "url": uri,
                    "title": getattr(web, "title", "Google Search source"),
                    "snippet": "",
                    "provider": "google_grounding",
                })
        if not sources:
            return {}
        return {"content": response.text or "", "sources": sources, "provider": "google_grounding"}
    except Exception as exc:  # Grounding availability varies by Vertex deployment.
        logger.info("[ResearchAgent] Google grounding unavailable: %s", exc)
        return {}


def legal_research_agent(state: Compliance_State) -> dict:
    """Gather source-backed regulatory evidence for detected risks.

    The agent performs multiple focused queries (one per detected issue, capped at
    three), deduplicates citations, and persists an auditable research bundle in
    the graph state for the grounded adjudication agent and frontend.
    """
    task_id = state["task_id"]
    step_name = "legal_research_agent"
    _tracker.start_step(task_id, step_name)
    result = state.get("result", {}) or {}

    try:
        reports: list[str] = []
        sources: list[dict[str, str]] = []
        provider = "none"
        for query in _queries(state, result):
            research = _google_grounded_research(query)
            if not research:
                research = tavily_compliance_research(query=query, task_id=task_id)
                if research:
                    provider = "tavily"
            else:
                provider = "google_grounding"
            if research.get("content"):
                reports.append(research["content"])
            sources.extend(research.get("sources", []))

        unique_sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for source in sources:
            url = source.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(source)

        result["_research_context"] = "\n\n".join(reports)
        result["_research_sources"] = unique_sources[:10]
        result["_research_provider"] = provider
        _tracker.complete_step(task_id, step_name, f"Collected {len(unique_sources)} regulatory sources via {provider}")
        return {"result": result}
    except Exception as exc:
        logger.exception("[ResearchAgent] Research failed: %s", exc)
        _tracker.fail_step(task_id, step_name, str(exc))
        result["_research_context"] = ""
        result["_research_sources"] = []
        result["_research_provider"] = "none"
        return {"result": result}


def grounded_compliance_agent(state: Compliance_State) -> dict:
    """Reconcile Gemini's initial findings against local rules and live evidence."""
    task_id = state["task_id"]
    step_name = "grounded_compliance_agent"
    _tracker.start_step(task_id, step_name)
    result = state.get("result", {}) or {}
    sources = result.get("_research_sources", [])

    try:
        if not sources or gemini is None:
            result["verification"] = {
                "research_report": result.get("_research_context") or "No regulatory research available for this content.",
                "sources": sources,
                "citation_urls": [],
                "sources_count": 0,
                "overall_confidence": "low",
                "violations_checked": len(result.get("high_risk_indicator", [])),
                "provider": result.get("_research_provider", "none"),
            }
            return {"result": result}

        prompt = f"""You are a platform-ad approval adjudicator. Reconcile the initial assessment with the cited evidence.
The verdict answers one practical question: is this creative likely to be accepted by the selected platform in the selected market?

Decision calibration:
- Use "rejected" only for a direct platform prohibition, a clearly applicable law, or an unambiguous safety/claim breach supported by a supplied source.
- Use "needs_remediation" only when a specific creative change is needed for a documented platform policy, such as an unsupported absolute claim, misleading presentation, or dangerous act.
- Use "accepted" when a concern is merely cultural/contextual and no supplied primary platform rule or law prohibits it. Put those concerns in localization_plan as optional local-market guidance, not as a violation.
- Do not invent rule IDs, statutory requirements, or rejection reasons. Do not treat a broad decency standard as an automatic platform rejection.
- Keep high_risk_indicator and violations_timeline only for documented, actionable findings. Each video timeline item must have a real non-zero time range matching its indicator.

Return only JSON matching the initial assessment shape.

MARKET: {state['market']}
PLATFORM: {state['platform']}
LOCAL RULES: {json.dumps(result.get('_rules', []), ensure_ascii=False)}
INITIAL ASSESSMENT: {json.dumps({k: v for k, v in result.items() if not k.startswith('_') and k != 'verification'}, ensure_ascii=False)}
RESEARCH: {result.get('_research_context', '')}
"""
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        adjudicated = parse_json_res(response.text)
        for key in (
            "risk_percentage", "risk_level", "compliance_verdict", "high_risk_indicator",
            "violations_timeline", "localization_plan", "explanation", "suggestion",
            "cultural_fit_score", "language_compliance", "image_review",
        ):
            if key in adjudicated:
                result[key] = adjudicated[key]
        result["verification"] = {
            "research_report": result.get("_research_context", ""),
            "sources": sources,
            "citation_urls": [source["url"] for source in sources if source.get("url")],
            "sources_count": len(sources),
            "overall_confidence": "high" if len(sources) >= 3 else "medium",
            "violations_checked": len(result.get("high_risk_indicator", [])),
            "provider": result.get("_research_provider", "tavily"),
        }
        _tracker.complete_step(task_id, step_name, f"Grounded {len(result.get('high_risk_indicator', []))} findings with {len(sources)} sources")
        return {"result": result}
    except Exception as exc:
        logger.exception("[ResearchAgent] Grounded adjudication failed: %s", exc)
        _tracker.fail_step(task_id, step_name, str(exc))
        return {"result": result}
