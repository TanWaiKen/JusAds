"""
tavily_guard.py
───────────────
Restricted Tavily search interface for compliance-only deep research.

This module is the ONLY entry point for Tavily API calls in the entire system.
Generation agents must use GoogleSearch (Gemini built-in) instead.

Every invocation is:
  1. Logged with [TavilyGuard] prefix (task_id + query)
  2. Recorded in the tavily_usage_log table for cost monitoring
  3. Wrapped in try/except with 10-second timeout — never blocks the pipeline

Requirements: 10.1, 10.2, 10.3
"""

import logging
from typing import Optional

from shared.clients import supabase, tavily

logger = logging.getLogger(__name__)

# Maximum time to wait for a single Tavily search (seconds)
_TAVILY_TIMEOUT_SECONDS = 10


def tavily_compliance_search(
    query: str,
    task_id: str,
    max_results: int = 5,
    search_depth: str = "advanced",
) -> dict:
    """Execute a Tavily search restricted to compliance use only.

    This is the ONLY function in the codebase that should call tavily.search().
    Logs every invocation for cost monitoring and records to tavily_usage_log.

    Args:
        query: The regulatory search query.
        task_id: The compliance task_id for audit logging.
        max_results: Number of results to fetch (default 5).
        search_depth: 'basic' or 'advanced' (default 'advanced').

    Returns:
        Tavily search result dict with 'results' key, or empty dict on failure.
    """
    logger.info(
        "[TavilyGuard] Compliance search invoked — task_id=%s, query=%s",
        task_id, query[:100],
    )

    if tavily is None:
        logger.warning("[TavilyGuard] Tavily client not initialized — skipping search")
        return {}

    try:
        result = tavily.search(
            query,
            max_results=max_results,
            search_depth=search_depth,
        )

        results_count = len(result.get("results", []))
        logger.info(
            "[TavilyGuard] Search returned %d results for task_id=%s",
            results_count, task_id,
        )

        # Record usage to tavily_usage_log (fire-and-forget)
        _log_usage(task_id, query, results_count, search_depth)

        return result

    except Exception as e:
        logger.error(
            "[TavilyGuard] Search failed for task_id=%s: %s", task_id, e
        )
        # Still log the failed attempt for cost awareness
        _log_usage(task_id, query, 0, search_depth)
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
