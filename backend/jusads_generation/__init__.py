"""
jusads_generation
──────────────────
Agentic Ad Studio generation module.

Restructures the legacy monolithic ``agent/generation_agent.py`` into a clean,
one-concern-per-file module: routing lives in ``routes/generation.py``,
orchestration in ``orchestrator.py``, each Media Agent under ``agents/``,
persistence in ``chat_store.py``, with supporting layers for state, platform
rules, intent detection, and compliance bridging (Req 1.1, 1.2, 1.3).

The orchestrator entrypoint (``run_generation``) is exported lazily via
``__getattr__`` so that importing this package does not fail before
``orchestrator.py`` is implemented in a later task.
"""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

__all__ = ["logger", "run_generation", "run_video_plan_execution"]

if TYPE_CHECKING:  # pragma: no cover - import hint for type checkers only
    from jusads_generation.orchestrator import run_generation, run_video_plan_execution


def __getattr__(name: str):
    """Lazily resolve the orchestrator entrypoint once it is implemented.

    Deferring the import keeps ``import jusads_generation`` working during the
    phased rollout, before ``orchestrator.py`` exists.
    """
    if name == "run_generation":
        from jusads_generation.orchestrator import run_generation

        return run_generation
    if name == "run_video_plan_execution":
        from jusads_generation.orchestrator import run_video_plan_execution

        return run_video_plan_execution
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
