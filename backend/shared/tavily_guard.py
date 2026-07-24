"""
tavily_guard.py
───────────────
Guarded Tavily research interface for compliance and generation fallback.

This module is the ONLY entry point for Tavily API calls in the entire system.
Generation agents use GoogleSearch first and may use the low-cost creative
fallback here when Google Search is unavailable.

Every invocation is:
  1. Logged with [TavilyGuard] prefix (task_id + query)
  2. Recorded in the tavily_usage_log table for cost monitoring
  3. Wrapped in try/except — never blocks the pipeline

Compliance research uses advanced search. Creative fallback uses basic search
with a small result limit to control latency and cost.
"""

import logging
from typing import Optional

from shared.clients import supabase, tavily
from shared.config import TAVILY_ENABLED

logger = logging.getLogger(__name__)

_CREATIVE_MAX_RESULTS = 3


def tavily_creative_search(
    query: str,
    task_id: str,
    market: str = "malaysia",
    language: str = "en",
) -> str:
    """Return compact creative context when Google Search is unavailable.

    This fallback deliberately uses Tavily's basic search depth and at most three
    results. Every call is logged against the generation task for cost
    monitoring. Failure never blocks ad generation.
    """
    logger.info(
        "[TavilyGuard] Creative fallback invoked — task_id=%s, market=%s, "
        "language=%s, query=%s",
        task_id,
        market,
        language,
        query[:100],
    )

    if not TAVILY_ENABLED:
        logger.info("[TavilyGuard] Tavily is disabled — skipping creative fallback")
        return ""

    if tavily is None:
        logger.warning("[TavilyGuard] Tavily client not initialized — skipping fallback")
        return ""

    try:
        result = tavily.search(
            query,
            max_results=_CREATIVE_MAX_RESULTS,
            search_depth="basic",
            topic="general",
            include_answer=True,
        )
        results = result.get("results", [])
        answer = (result.get("answer") or "").strip()
        _log_usage(task_id, f"[CREATIVE_FALLBACK] {query}", len(results), "basic")

        if not answer and not results:
            logger.warning("[TavilyGuard] Creative fallback returned no results")
            return ""

        context_parts: list[str] = []
        if answer:
            context_parts.append(answer)

        for item in results[:_CREATIVE_MAX_RESULTS]:
            title = (item.get("title") or "Source").strip()
            snippet = (item.get("content") or "").strip()
            url = (item.get("url") or "").strip()
            if not snippet:
                continue
            source_suffix = f" ({url})" if url else ""
            context_parts.append(f"{title}: {snippet[:600]}{source_suffix}")

        context = "\n".join(context_parts).strip()
        logger.info(
            "[TavilyGuard] Creative fallback returned %d sources and %d chars",
            len(results),
            len(context),
        )
        return context
    except Exception as e:
        logger.warning(
            "[TavilyGuard] Creative fallback failed for task_id=%s: %s",
            task_id,
            e,
        )
        _log_usage(task_id, f"[CREATIVE_FALLBACK] {query}", 0, "basic")
        return ""


def tavily_compliance_research(
    query: str,
    task_id: str,
) -> dict:
    """Execute Tavily deep research for compliance analysis.
    
    Returns a comprehensive research report with synthesized content and sources.
    This is the ONLY Tavily function exposed in the compliance system.
    
    Args:
        query: The regulatory search query.
        task_id: The compliance task_id for audit logging.
        
    Returns:
        Dict with 'content' (full research report) and 'sources' (list of dict with url/title/snippet).
    """
    logger.info(
        "[TavilyGuard] Compliance research invoked — task_id=%s, query=%s",
        task_id, query[:100],
    )
    
    if tavily is None:
        logger.warning("[TavilyGuard] Tavily client not initialized — skipping research")
        return {}
        
    try:
        # Use advanced search with 10 results for comprehensive research
        result = tavily.search(
            query,
            max_results=10,
            search_depth="advanced",
            include_answer=True,  # Get AI-generated answer if available
        )
        
        results = result.get("results", [])
        answer = result.get("answer", "")
        
        if not results:
            logger.warning("[TavilyGuard] Research returned no results")
            _log_usage(task_id, f"[RESEARCH] {query}", 0, "research")
            return {}
            
        # Synthesize research content from results
        content_parts = []
        if answer:
            content_parts.append(f"## Summary\n\n{answer}\n")
        
        content_parts.append("## Sources\n")
        for i, r in enumerate(results[:8], 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            snippet = r.get("content", "")
            if title and snippet:
                content_parts.append(f"### {i}. {title}\n{snippet}\n**Source:** {url}\n")
        
        research_content = "\n".join(content_parts)
        
        # Format sources
        sources = [
            {"url": r.get("url"), "title": r.get("title"), "snippet": r.get("content", "")[:200]}
            for r in results
            if r.get("url")
        ]
        
        logger.info("[TavilyGuard] Research complete: %d sources", len(sources))
        _log_usage(task_id, f"[RESEARCH] {query}", len(sources), "research")
        
        return {
            "content": research_content,
            "sources": sources,
        }
        
    except Exception as e:
        logger.error(
            "[TavilyGuard] Research failed for task_id=%s: %s", task_id, e
        )
        _log_usage(task_id, f"[RESEARCH] {query}", 0, "research")
        return {}


def _log_usage(
    task_id: str,
    query: str,
    results_count: int,
    search_depth: str,
) -> None:
    """Record Tavily usage to the tavily_usage_log table (fire-and-forget).

    Never raises — logging failures are swallowed to avoid blocking the pipeline.
    """
    try:
        supabase.table("tavily_usage_log").insert({
            "task_id": task_id,
            "query": query[:500],  # Truncate long queries
            "results_count": results_count,
            "search_depth": search_depth,
        }).execute()
    except Exception as e:
        logger.warning(
            "[TavilyGuard] Failed to log usage for task_id=%s: %s",
            task_id, e,
        )

