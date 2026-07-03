"""
pipeline_runner.py
──────────────────
Runs LangGraph pipelines (Compliance and Remediation) and persists real-time
progress to the pipeline_progress Supabase table via ProgressTracker.

Responsibilities:
  - Stream pipeline execution node-by-node
  - Call tracker.start_step() before each node executes
  - Call tracker.complete_step() after each node completes
  - Call tracker.fail_step() when a node raises an exception
  - Handle GraphInterrupt for Remediation Pipeline human-in-the-loop confirmation
  - Ensure no WebSocket connections are established, maintained, or used
  - Integrate with pending_decisions/decision_store for human-in-the-loop flow

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

import asyncio
import logging
from typing import Dict, Optional, Union

from langgraph.types import Command

from shared.models import Compliance_State, Remediation_State
from jusads_compliance.progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

# Human-readable descriptions for each pipeline node
NODE_DESCRIPTIONS = {
    # Compliance Pipeline nodes
    "fetch_rules_and_personas": "Fetching regulatory rules and cultural personas",
    "transcribe_media": "Transcribing audio/video media content",
    "main_brain_analysis": "Running AI compliance analysis on media content",
    "judges_agent": "Evaluating for bias and hallucination",
    "decision_router": "Routing compliance decision",
    # Remediation Pipeline nodes
    "fetch_compliance_result": "Retrieving compliance check result",
    "confirm_aspect_ratio": "Confirming target aspect ratio with user",
    "media_remediation": "Performing media-specific remediation",
    "upload_and_finalize": "Uploading remediated assets and finalizing",
    # Legacy node names (retained for backward compatibility)
    "compliance_check": "Running compliance analysis on media content",
    "segment_image": "Segmenting non-compliant regions in image",
    "extract_clips": "Extracting violation clips from video",
    "verify_violations": "Verifying violations against regulatory sources",
    "judge_hallucination": "Evaluating for bias and hallucination",
    "human_review": "Awaiting human review and approval",
    "finalize": "Finalizing compliance check result",
    "remix_router": "Routing to media-specific remediation tool",
    "remix_finalize": "Validating remediation quality",
}

# Type alias for pipeline state (either Compliance or Remediation)
PipelineState = Union[Compliance_State, Remediation_State, dict]


def _get_compliance_pipeline():
    """Lazy import of the compiled compliance pipeline."""
    from jusads_compliance.compliance_pipeline import compliance_pipeline
    return compliance_pipeline


def _get_remediation_pipeline():
    """Lazy import of the compiled remediation pipeline."""
    from jusads_compliance.remediation_pipeline import remediation_pipeline
    return remediation_pipeline


class PipelineRunner:
    """Runs LangGraph pipelines and tracks progress via ProgressTracker.

    Integrates with pending_decisions/decision_store dicts for the human-in-the-loop
    flow: when the pipeline hits a GraphInterrupt, it creates an asyncio.Event and
    waits for the event to be set (by the resume endpoint).

    Usage:
        tracker = ProgressTracker()
        runner = PipelineRunner(tracker=tracker)
        result = await runner.run(check_id, state)

        # Or for a full end-to-end flow that blocks until human responds:
        result = await runner.run_with_human_loop(check_id, state)
    """

    def __init__(
        self,
        tracker: Optional[ProgressTracker] = None,
        pipeline=None,
        pending_decisions: Optional[Dict[str, asyncio.Event]] = None,
        decision_store: Optional[Dict[str, str]] = None,
    ):
        self.tracker = tracker or ProgressTracker()
        self._pipeline = pipeline
        self.pending_decisions = pending_decisions if pending_decisions is not None else {}
        self.decision_store = decision_store if decision_store is not None else {}

    @property
    def pipeline(self):
        """Get the compiled compliance pipeline (lazy-loaded if not injected)."""
        if self._pipeline is None:
            self._pipeline = _get_compliance_pipeline()
        return self._pipeline

    async def run(
        self,
        check_id: str,
        state: PipelineState,
        thread_id: Optional[str] = None,
    ) -> Optional[PipelineState]:
        """Run a pipeline, persisting progress for each node via ProgressTracker.

        Args:
            check_id: The compliance check identifier (used for progress tracking).
            state: The initial pipeline state to feed into the graph.
            thread_id: Optional LangGraph thread ID for checkpointing.

        Returns:
            The final pipeline state on success, or None if a fatal error occurred.
        """
        from langgraph.errors import GraphInterrupt

        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state: Optional[PipelineState] = None

        try:
            for event in self.pipeline.stream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # Track step start
                    self.tracker.start_step(check_id, node_name)

                    # Track step completion
                    description = NODE_DESCRIPTIONS.get(
                        node_name, f"Completed {node_name}"
                    )
                    self.tracker.complete_step(check_id, node_name, description)

                    # Track state updates
                    if isinstance(node_output, dict):
                        if final_state is None:
                            final_state = node_output
                        else:
                            # Merge partial state updates
                            if isinstance(final_state, dict):
                                final_state.update(node_output)

                    logger.info(
                        "[PipelineRunner] Node '%s' completed for check_id=%s",
                        node_name, check_id,
                    )

        except GraphInterrupt as interrupt_exc:
            # Pipeline hit an interrupt (human-in-the-loop)
            logger.info(
                "[PipelineRunner] GraphInterrupt for check_id=%s", check_id
            )
            self._handle_graph_interrupt_tracking(check_id, interrupt_exc)
            return None

        except Exception as e:
            node_name = _extract_node_from_exception(e)
            error_message = str(e)[:200]
            logger.error(
                "[PipelineRunner] Pipeline error for check_id=%s at node=%s: %s",
                check_id, node_name, e,
                exc_info=True,
            )
            self.tracker.fail_step(check_id, node_name, error_message)
            return None

        return final_state

    async def run_with_human_loop(
        self,
        check_id: str,
        state: PipelineState,
        thread_id: Optional[str] = None,
        timeout: float = 300.0,
    ) -> Optional[PipelineState]:
        """Run the pipeline end-to-end, blocking at interrupts until a decision arrives.

        This method integrates with pending_decisions and decision_store:
        1. Starts the pipeline streaming
        2. When GraphInterrupt occurs, tracks it via ProgressTracker
        3. Creates an asyncio.Event and waits for it to be set (by resume endpoint)
        4. Once set, resumes the pipeline with the stored decision
        5. Continues streaming until completion

        Args:
            check_id: The compliance check identifier.
            state: The initial pipeline state.
            thread_id: Optional thread ID for checkpointing.
            timeout: Maximum seconds to wait for human decision (default 5 minutes).

        Returns:
            The final pipeline state, or None if interrupted/errored/timed out.
        """
        from langgraph.errors import GraphInterrupt

        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state: Optional[PipelineState] = None

        try:
            # Phase 1: Run pipeline until interrupt or completion
            for event in self.pipeline.stream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    self.tracker.start_step(check_id, node_name)

                    description = NODE_DESCRIPTIONS.get(
                        node_name, f"Completed {node_name}"
                    )
                    self.tracker.complete_step(check_id, node_name, description)

                    if isinstance(node_output, dict):
                        if final_state is None:
                            final_state = node_output
                        elif isinstance(final_state, dict):
                            final_state.update(node_output)

                    logger.info(
                        "[PipelineRunner] Node '%s' completed for check_id=%s",
                        node_name, check_id,
                    )

        except GraphInterrupt as interrupt_exc:
            # Pipeline hit an interrupt — track it and wait for decision
            self._handle_graph_interrupt_tracking(check_id, interrupt_exc)

            # Create an asyncio.Event for this check_id and wait
            event = asyncio.Event()
            self.pending_decisions[check_id] = event

            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "[PipelineRunner] Human decision timed out for check_id=%s",
                    check_id,
                )
                self.tracker.fail_step(
                    check_id, "human_review",
                    "Human review timed out — no decision received",
                )
                return None
            finally:
                self.pending_decisions.pop(check_id, None)

            # Retrieve the stored decision and resume the pipeline
            decision = self.decision_store.pop(check_id, "ok")
            logger.info(
                "[PipelineRunner] Resuming pipeline for check_id=%s with decision=%s",
                check_id, decision,
            )

            # Phase 2: Resume pipeline with the decision
            return await self.resume(check_id, decision, thread_id=thread_id)

        except Exception as e:
            node_name = _extract_node_from_exception(e)
            error_message = str(e)[:200]
            logger.error(
                "[PipelineRunner] Pipeline error for check_id=%s at node=%s: %s",
                check_id, node_name, e,
                exc_info=True,
            )
            self.tracker.fail_step(check_id, node_name, error_message)
            return None

        return final_state

    async def resume(
        self,
        check_id: str,
        decision: str,
        thread_id: Optional[str] = None,
    ) -> Optional[PipelineState]:
        """Resume a pipeline that was interrupted (e.g., human-in-the-loop).

        Args:
            check_id: The compliance check identifier.
            decision: The human decision (e.g., "ok" or "edit").
            thread_id: Optional thread ID for checkpointing.

        Returns:
            The final pipeline state, or None if another interrupt/error occurred.
        """
        from langgraph.errors import GraphInterrupt

        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state: Optional[PipelineState] = None

        try:
            # Resume the pipeline with the human decision via Command
            for event in self.pipeline.stream(
                Command(resume=decision), config=config, stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    self.tracker.start_step(check_id, node_name)

                    description = NODE_DESCRIPTIONS.get(
                        node_name, f"Completed {node_name}"
                    )
                    self.tracker.complete_step(check_id, node_name, description)

                    if isinstance(node_output, dict):
                        if final_state is None:
                            final_state = node_output
                        elif isinstance(final_state, dict):
                            final_state.update(node_output)

                    logger.info(
                        "[PipelineRunner] Resumed node '%s' completed for check_id=%s",
                        node_name, check_id,
                    )

        except GraphInterrupt as interrupt_exc:
            self._handle_graph_interrupt_tracking(check_id, interrupt_exc)
            return None

        except Exception as e:
            node_name = _extract_node_from_exception(e)
            error_message = str(e)[:200]
            logger.error(
                "[PipelineRunner] Pipeline resume error for check_id=%s: %s",
                check_id, e,
                exc_info=True,
            )
            self.tracker.fail_step(check_id, node_name, error_message)
            return None

        return final_state

    # ── Private helpers ───────────────────────────────────────────────────────

    def _handle_graph_interrupt_tracking(
        self, check_id: str, interrupt_exc
    ) -> None:
        """Track a GraphInterrupt via ProgressTracker.

        Extracts the interrupt payload and records the step as requiring
        human input. The step is tracked as 'running' (awaiting decision).
        """
        interrupt_value = _extract_interrupt_value(interrupt_exc)

        message = "Awaiting human confirmation"
        if isinstance(interrupt_value, dict):
            message = interrupt_value.get("message", message)

        # Record the interrupt step as running (awaiting human input)
        self.tracker.start_step(check_id, "human_review")
        logger.info(
            "[PipelineRunner] Interrupt recorded for check_id=%s: %s",
            check_id, message,
        )


# ── Module-level helpers ──────────────────────────────────────────────────────


def _extract_interrupt_value(interrupt_exc) -> dict:
    """Extract the interrupt payload from a GraphInterrupt exception.

    Returns a dict with interrupt details, or empty dict if extraction fails.
    """
    interrupt_value = {}

    if hasattr(interrupt_exc, "interrupts") and interrupt_exc.interrupts:
        # Older LangGraph: GraphInterrupt.interrupts is a list of Interrupt objects
        first_interrupt = interrupt_exc.interrupts[0]
        if hasattr(first_interrupt, "value"):
            interrupt_value = first_interrupt.value
    elif interrupt_exc.args and isinstance(interrupt_exc.args[0], list) and interrupt_exc.args[0]:
        # Newer LangGraph: args[0] is a list of Interrupt namedtuples
        first_interrupt = interrupt_exc.args[0][0]
        if hasattr(first_interrupt, "value"):
            interrupt_value = first_interrupt.value
    elif interrupt_exc.args:
        interrupt_value = interrupt_exc.args[0] if interrupt_exc.args else {}

    return interrupt_value if isinstance(interrupt_value, dict) else {}


def _extract_node_from_exception(exc: Exception) -> str:
    """Try to extract the failing node name from an exception.

    LangGraph exceptions sometimes include node context.
    Falls back to "unknown" if we can't determine it.
    """
    if hasattr(exc, "node"):
        return exc.node
    exc_str = str(exc)
    for node_name in NODE_DESCRIPTIONS:
        if node_name in exc_str:
            return node_name
    return "unknown"


def _build_result_payload(state: PipelineState) -> dict:
    """Build a result payload from a completed pipeline state.

    Returns a dictionary suitable for API responses.
    """
    if isinstance(state, dict):
        return {
            "status": state.get("status", "unknown"),
            "result": state.get("result", {}),
            "iteration": state.get("iteration", 0),
            "media_type": state.get("media_type", ""),
            "market": state.get("market", ""),
        }
    return {}
