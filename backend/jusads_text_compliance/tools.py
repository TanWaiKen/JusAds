"""LangGraph ReAct-compatible tool for text compliance checking.

Usage with LangGraph ReAct agent:

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langgraph.prebuilt import create_react_agent
    from jusads_text_compliance.tools import check_text_compliance

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    agent = create_react_agent(llm, tools=[check_text_compliance])
    result = agent.invoke({"messages": [("user", "Check if this ad is OK: ...")]})
"""

import json
import logging

from langchain_core.tools import tool

from .text_checker import TextComplianceChecker

logger = logging.getLogger(__name__)

# Lazy singleton — created on first call
_checker: TextComplianceChecker | None = None


def _get_checker() -> TextComplianceChecker:
    global _checker
    if _checker is None:
        _checker = TextComplianceChecker()
    return _checker


@tool
def check_text_compliance(
    ad_text: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages",
) -> str:
    """Check advertising text for regulatory and cultural compliance in Malaysia/Singapore.

    Evaluates ad copy against MCMC regulatory guidelines and cultural
    sensitivities for Malay, Chinese, and Indian audiences.

    Args:
        ad_text: The advertisement text to evaluate.
        market: Target market — "malaysia" or "singapore".
        ethnicity: Target ethnicity — "malay", "chinese", "indian", or "all".
        age_group: Target age group — "all_ages", "adults_only", or "children".

    Returns:
        JSON string with risk_level, score (0-100), violations, explanation,
        and suggestion.
    """
    checker = _get_checker()
    result = checker.check_compliance(
        ad_text=ad_text,
        market=market,
        ethnicity=ethnicity,
        age_group=age_group,
    )

    # Return a concise JSON summary (strip bulky rule lists for agent consumption)
    summary = {
        "risk_level": result["risk_level"],
        "score": result["score"],
        "violations": result["violations"],
        "explanation": result["explanation"],
        "suggestion": result["suggestion"],
        "processing_time_ms": result["processing_time_ms"],
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)
