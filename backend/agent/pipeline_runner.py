"""
pipeline_runner.py
──────────────────
Runs the LangGraph compliance pipeline and emits real-time WebSocket events
via the ConnectionManager after each node transition.

Responsibilities:
  - Stream pipeline execution node-by-node
  - Emit `node_status` events after each node completes
  - Emit `interrupt` event when the pipeline reaches the human_review node
  - Emit `result` event when the pipeline completes
  - Emit `error` event when a node raises an exception
  - Ensure exceptions do NOT crash the server (graceful degradation)
  - Integrate with pending_decisions/decision_store for human-in-the-loop flow

Requirements: 1.1, 1.2, 1.3, 1.6
"""

import asyncio
import logging
from typing import Dict, Optional

from langgraph.types import Command

from agent.data_model import ComplianceState
from agent.ws_manager import ConnectionManager
from agent.progress import drain_progress

logger = logging.getLogger(__name__)

# Human-readable descriptions for each pipeline node
NODE_DESCRIPTIONS = {
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


def _get_pipeline():
    """Lazy import of the compiled pipeline to avoid heavy import chain at module level."""
    from agent.pipeline import compliance_pipeline
    return compliance_pipeline


class PipelineRunner:
    """Wraps the LangGraph compliance pipeline and emits WebSocket events.

    Integrates with pending_decisions/decision_store dicts for the human-in-the-loop
    flow: when the pipeline hits human_review, it sends an interrupt via WebSocket,
    creates an asyncio.Event, and waits for the event to be set (by handle_resume).

    Usage:
        runner = PipelineRunner(manager, pending_decisions, decision_store)
        result = await runner.run(check_id, state)

        # Or for a full end-to-end flow that blocks until human responds:
        result = await runner.run_with_human_loop(check_id, state)
    """

    def __init__(
        self,
        manager: ConnectionManager,
        pipeline=None,
        pending_decisions: Optional[Dict[str, asyncio.Event]] = None,
        decision_store: Optional[Dict[str, str]] = None,
    ):
        self.manager = manager
        self._pipeline = pipeline
        self.pending_decisions = pending_decisions if pending_decisions is not None else {}
        self.decision_store = decision_store if decision_store is not None else {}

    @property
    def pipeline(self):
        """Get the compiled pipeline (lazy-loaded if not injected)."""
        if self._pipeline is None:
            self._pipeline = _get_pipeline()
        return self._pipeline

    async def run(
        self,
        check_id: str,
        state: ComplianceState,
        thread_id: Optional[str] = None,
    ) -> Optional[ComplianceState]:
        """Run the compliance pipeline, emitting WebSocket events for each node.

        Args:
            check_id: The compliance check identifier (used for WebSocket routing).
            state: The initial ComplianceState to feed into the pipeline.
            thread_id: Optional LangGraph thread ID for checkpointing.

        Returns:
            The final ComplianceState on success, or None if a fatal error occurred.
        """
        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state = None

        try:
            # Stream the pipeline execution node-by-node
            for event in self.pipeline.stream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    await self._handle_node_completion(check_id, node_name, node_output)
                    # Track the latest state
                    if node_output and isinstance(node_output, ComplianceState):
                        final_state = node_output

        except Exception as e:
            # Check if this is a LangGraph interrupt (human_review node)
            if _is_interrupt_exception(e):
                await self._handle_interrupt(check_id, state, config)
                return None
            else:
                # Unexpected error — emit error event but do NOT crash
                node_name = _extract_node_from_exception(e)
                error_message = str(e)[:200]  # Cap at 200 chars
                logger.error(
                    f"Pipeline error for check_id={check_id} at node={node_name}: {e}",
                    exc_info=True,
                )
                await self.manager.send_error(
                    check_id, node_name, error_message, can_continue=False
                )
                return None

        # Pipeline completed successfully — emit result
        if final_state is not None:
            result_data = _build_result_payload(final_state)
            await self.manager.send_result(check_id, result_data)

        return final_state

    async def run_streaming(
        self,
        check_id: str,
        state: ComplianceState,
        thread_id: Optional[str] = None,
    ) -> Optional[ComplianceState]:
        """Run the pipeline with full streaming and interrupt handling.

        This method handles the LangGraph interrupt mechanism properly by
        catching the GraphInterrupt and emitting the interrupt event to
        the WebSocket client.

        Args:
            check_id: The compliance check identifier.
            state: The initial ComplianceState.
            thread_id: Optional thread ID for checkpointing.

        Returns:
            The final ComplianceState, or None if interrupted/errored.
        """
        from langgraph.errors import GraphInterrupt

        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state = None

        try:
            for event in self.pipeline.stream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # Emit node_status for each completed node
                    description = NODE_DESCRIPTIONS.get(
                        node_name, f"Completed {node_name}"
                    )
                    await self.manager.broadcast_node_status(
                        check_id, node_name, "completed", description
                    )

                    # Track state updates
                    if isinstance(node_output, ComplianceState):
                        final_state = node_output
                    elif isinstance(node_output, dict):
                        # LangGraph often returns partial state dicts
                        if final_state is None:
                            final_state = state
                        # Merge dict updates into state (for tracking)
                        for key, value in node_output.items():
                            if hasattr(final_state, key):
                                setattr(final_state, key, value)

        except GraphInterrupt as interrupt_exc:
            # Pipeline hit the human_review interrupt — emit interrupt event
            await self._handle_graph_interrupt(check_id, interrupt_exc, state)
            return None

        except Exception as e:
            # Node exception — emit error event, do NOT crash
            node_name = _extract_node_from_exception(e)
            error_message = str(e)[:200]
            logger.error(
                f"Pipeline error for check_id={check_id} at node={node_name}: {e}",
                exc_info=True,
            )
            await self.manager.send_error(
                check_id, node_name, error_message, can_continue=False
            )
            return None

        # Pipeline completed — emit result
        if final_state is not None:
            result_data = _build_result_payload(final_state)
            await self.manager.send_result(check_id, result_data)

        return final_state

    async def run_with_human_loop(
        self,
        check_id: str,
        state: ComplianceState,
        thread_id: Optional[str] = None,
        timeout: float = 300.0,
    ) -> Optional[ComplianceState]:
        """Run the pipeline end-to-end, blocking at human_review until a decision arrives.

        This method integrates with pending_decisions and decision_store:
        1. Starts the pipeline streaming
        2. When GraphInterrupt occurs (human_review), sends interrupt via WS
        3. Creates an asyncio.Event and waits for it to be set (by handle_resume)
        4. Once set, resumes the pipeline with the stored decision
        5. Continues streaming until completion

        Args:
            check_id: The compliance check identifier.
            state: The initial ComplianceState.
            thread_id: Optional thread ID for checkpointing.
            timeout: Maximum seconds to wait for human decision (default 5 minutes).

        Returns:
            The final ComplianceState, or None if interrupted/errored/timed out.
        """
        from langgraph.errors import GraphInterrupt

        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state = None

        try:
            # Phase 1: Run pipeline until interrupt or completion
            for event in self.pipeline.stream(state, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # Drain and send buffered progress messages from the node
                    progress_messages = drain_progress()
                    for msg in progress_messages:
                        await self.manager.send_message(check_id, {
                            "type": "progress",
                            "message": msg,
                        })

                    description = NODE_DESCRIPTIONS.get(
                        node_name, f"Completed {node_name}"
                    )
                    await self.manager.broadcast_node_status(
                        check_id, node_name, "completed", description
                    )

                    if isinstance(node_output, ComplianceState):
                        final_state = node_output
                    elif isinstance(node_output, dict):
                        if final_state is None:
                            final_state = state
                        for key, value in node_output.items():
                            if hasattr(final_state, key):
                                setattr(final_state, key, value)

        except GraphInterrupt as interrupt_exc:
            # Pipeline hit human_review — send interrupt and wait for decision
            await self._handle_graph_interrupt(check_id, interrupt_exc, state)

            # Create an asyncio.Event for this check_id and wait
            event = asyncio.Event()
            self.pending_decisions[check_id] = event

            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Human decision timed out for check_id={check_id}")
                await self.manager.send_error(
                    check_id, "human_review",
                    "Human review timed out — no decision received",
                    can_continue=False,
                )
                return None
            finally:
                self.pending_decisions.pop(check_id, None)

            # Retrieve the stored decision and resume the pipeline
            decision = self.decision_store.pop(check_id, "ok")
            logger.info(f"Resuming pipeline for check_id={check_id} with decision={decision}")

            # Phase 2: Resume pipeline with the decision
            return await self.resume(check_id, decision, thread_id=thread_id)

        except Exception as e:
            node_name = _extract_node_from_exception(e)
            error_message = str(e)[:200]
            logger.error(
                f"Pipeline error for check_id={check_id} at node={node_name}: {e}",
                exc_info=True,
            )
            await self.manager.send_error(
                check_id, node_name, error_message, can_continue=False
            )
            return None

        # Pipeline completed without interrupt — emit result
        if final_state is not None:
            result_data = _build_result_payload(final_state)
            await self.manager.send_result(check_id, result_data)

        return final_state

    async def resume(
        self,
        check_id: str,
        decision: str,
        thread_id: Optional[str] = None,
    ) -> Optional[ComplianceState]:
        """Resume a pipeline that was interrupted at human_review.

        Args:
            check_id: The compliance check identifier.
            decision: The human decision ("ok" or "edit").
            thread_id: Optional thread ID for checkpointing.

        Returns:
            The final ComplianceState, or None if another interrupt/error occurred.
        """
        from langgraph.errors import GraphInterrupt

        config = {"configurable": {"thread_id": thread_id or check_id}}
        final_state = None

        try:
            # Resume the pipeline with the human decision via Command
            for event in self.pipeline.stream(
                Command(resume=decision), config=config, stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    description = NODE_DESCRIPTIONS.get(
                        node_name, f"Completed {node_name}"
                    )
                    await self.manager.broadcast_node_status(
                        check_id, node_name, "completed", description
                    )

                    if isinstance(node_output, ComplianceState):
                        final_state = node_output
                    elif isinstance(node_output, dict) and final_state is not None:
                        for key, value in node_output.items():
                            if hasattr(final_state, key):
                                setattr(final_state, key, value)

        except GraphInterrupt as interrupt_exc:
            await self._handle_graph_interrupt(check_id, interrupt_exc, None)
            return None

        except Exception as e:
            node_name = _extract_node_from_exception(e)
            error_message = str(e)[:200]
            logger.error(
                f"Pipeline resume error for check_id={check_id}: {e}",
                exc_info=True,
            )
            await self.manager.send_error(
                check_id, node_name, error_message, can_continue=False
            )
            return None

        # Pipeline completed after resume — emit result
        if final_state is not None:
            result_data = _build_result_payload(final_state)
            await self.manager.send_result(check_id, result_data)

        return final_state

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _handle_node_completion(
        self, check_id: str, node_name: str, node_output
    ) -> None:
        """Emit a node_status event after a node completes."""
        description = NODE_DESCRIPTIONS.get(node_name, f"Completed {node_name}")
        await self.manager.broadcast_node_status(
            check_id, node_name, "completed", description
        )

    async def _handle_interrupt(
        self, check_id: str, state: ComplianceState, config: dict
    ) -> None:
        """Handle the pipeline interrupt at human_review node."""
        # Build interrupt payload from the current state
        result = state.result if hasattr(state, "result") else {}
        await self.manager.send_interrupt(
            check_id,
            "Compliance check complete. Please review the result.",
            result,
            ["ok", "edit"],
        )

    async def _handle_graph_interrupt(
        self, check_id: str, interrupt_exc, state: Optional[ComplianceState]
    ) -> None:
        """Handle a LangGraph GraphInterrupt exception.

        Extracts the interrupt payload and sends it as a WebSocket interrupt event.
        """
        # LangGraph GraphInterrupt carries the interrupt value in its args
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

        message = "Compliance check complete. Please review the result."
        result = {}
        options = ["ok", "edit"]

        if isinstance(interrupt_value, dict):
            message = interrupt_value.get("message", message)
            result = interrupt_value.get("result", result)
            options = interrupt_value.get("options", options)

        await self.manager.send_interrupt(check_id, message, result, options)


# ── Module-level helpers ──────────────────────────────────────────────────────


def _is_interrupt_exception(exc: Exception) -> bool:
    """Check if an exception is a LangGraph interrupt."""
    try:
        from langgraph.errors import GraphInterrupt
        return isinstance(exc, GraphInterrupt)
    except ImportError:
        # Fallback: check by class name
        return type(exc).__name__ == "GraphInterrupt"


def _extract_node_from_exception(exc: Exception) -> str:
    """Try to extract the failing node name from an exception.

    LangGraph exceptions sometimes include node context.
    Falls back to "unknown" if we can't determine it.
    """
    # Check if the exception has node information attached
    if hasattr(exc, "node"):
        return exc.node
    # Check traceback for node function names
    exc_str = str(exc)
    for node_name in NODE_DESCRIPTIONS:
        if node_name in exc_str:
            return node_name
    return "unknown"


def _build_result_payload(state: ComplianceState) -> dict:
    """Build the final result payload from a completed ComplianceState.

    Returns a dictionary suitable for sending via WebSocket as a result event.
    """
    result = state.result if hasattr(state, "result") else {}
    return {
        "status": state.status if hasattr(state, "status") else "unknown",
        "result": result,
        "iteration": state.iteration if hasattr(state, "iteration") else 0,
        "media_type": state.media_type if hasattr(state, "media_type") else "",
        "market": state.market if hasattr(state, "market") else "",
    }
