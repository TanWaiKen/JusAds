"""Unit tests for creative search provider fallback."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jusads_generation.search_tools import search_creative_context
from shared.tavily_guard import tavily_creative_search


def test_google_search_result_does_not_call_tavily() -> None:
    gemini = Mock()
    gemini.models.generate_content.return_value = SimpleNamespace(text="Google context")

    with patch("jusads_generation.search_tools.gemini", gemini), patch(
        "jusads_generation.search_tools.tavily_creative_search"
    ) as fallback:
        result = asyncio.run(
            search_creative_context("coffee trends", task_id="task-123")
        )

    assert result == "Google context"
    fallback.assert_not_called()


def test_google_search_error_falls_back_to_tavily() -> None:
    gemini = Mock()
    gemini.models.generate_content.side_effect = RuntimeError(
        "429 RESOURCE_EXHAUSTED"
    )

    with patch("jusads_generation.search_tools.gemini", gemini), patch(
        "jusads_generation.search_tools.tavily_creative_search",
        return_value="Tavily context",
    ) as fallback:
        result = asyncio.run(
            search_creative_context(
                "coffee trends",
                market="malaysia",
                language="en",
                task_id="task-123",
            )
        )

    assert result == "Tavily context"
    fallback.assert_called_once_with(
        query="coffee trends",
        task_id="task-123",
        market="malaysia",
        language="en",
    )


def test_empty_google_search_result_falls_back_to_tavily() -> None:
    gemini = Mock()
    gemini.models.generate_content.return_value = SimpleNamespace(text="")

    with patch("jusads_generation.search_tools.gemini", gemini), patch(
        "jusads_generation.search_tools.tavily_creative_search",
        return_value="Fallback context",
    ):
        result = asyncio.run(
            search_creative_context("coffee trends", task_id="task-123")
        )

    assert result == "Fallback context"


def test_tavily_creative_search_formats_and_audits_results() -> None:
    client = Mock()
    client.search.return_value = {
        "answer": "Coffee ads favor sensory hooks.",
        "results": [
            {
                "title": "Coffee campaign ideas",
                "content": "Use aroma, ritual, and morning-routine storytelling.",
                "url": "https://example.com/coffee",
            }
        ],
    }

    with patch("shared.tavily_guard.tavily", client), patch(
        "shared.tavily_guard._log_usage"
    ) as log_usage:
        result = tavily_creative_search(
            "coffee advertising trends",
            task_id="task-123",
        )

    assert "Coffee ads favor sensory hooks." in result
    assert "Coffee campaign ideas" in result
    client.search.assert_called_once_with(
        "coffee advertising trends",
        max_results=3,
        search_depth="basic",
        topic="general",
        include_answer=True,
    )
    log_usage.assert_called_once_with(
        "task-123",
        "[CREATIVE_FALLBACK] coffee advertising trends",
        1,
        "basic",
    )


def test_tavily_creative_search_respects_disabled_flag() -> None:
    client = Mock()

    with patch("shared.tavily_guard.TAVILY_ENABLED", False), patch(
        "shared.tavily_guard.tavily", client
    ):
        result = tavily_creative_search(
            "coffee advertising trends",
            task_id="task-123",
        )

    assert result == ""
    client.search.assert_not_called()
