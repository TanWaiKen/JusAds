"""
test_pipeline_runner.py
───────────────────────
Unit tests for the PipelineRunner WebSocket integration.

Tests verify that:
  - Node transitions emit node_status events
  - Interrupt at human_review emits interrupt event
  - Successful completion emits result event
  - Node exceptions emit error event without crashing
  - Pipeline continues serving after exceptions
  - run_with_human_loop integrates with pending_decisions/decision_store
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

from agent.ws_manager import ConnectionManager
from agent.pipeline_runner import (
    PipelineRunner,
    NODE_DESCRIPTIONS,
    _build_result_payload,
    _is_interrupt_exception,
    _extract_node_from_exception,
)
from agent.data_model import ComplianceState


@pytest.fixture
def manager():
    """Create a ConnectionManager with mock WebSocket methods."""
    mgr = ConnectionManager()
    mgr.broadcast_node_status = AsyncMock()
    mgr.send_interrupt = AsyncMock()
    mgr.send_result = AsyncMock()
    mgr.send_error = AsyncMock()
    return mgr


@pytest.fixture
def mock_pipeline():
    """Create a mock pipeline object with a stream method."""
    pipeline = MagicMock()
    return pipeline


@pytest.fixture
def pending_decisions():
    """Shared pending_decisions dict for human-in-the-loop tests."""
    return {}


@pytest.fixture
def decision_store():
    """Shared decision_store dict for human-in-the-loop tests."""
    return {}


@pytest.fixture
def runner(manager, mock_pipeline, pending_decisions, decision_store):
    """Create a PipelineRunner with mocked manager and injected pipeline."""
    return PipelineRunner(
        manager,
        pipeline=mock_pipeline,
        pending_decisions=pending_decisions,
        decision_store=decision_store,
    )


@pytest.fixture
def sample_state():
    """Create a sample ComplianceState for testing."""
    return ComplianceState(
        session_id="test-session",
        media_type="text",
        input_path="",
        text_input="Test ad content for compliance checking",
        market="malaysia",
        platform="tiktok",
        ethnicity="malay",
        age_group="gen_z",
    )


# ── Test node_status emission on node transitions ─────────────────────────────


@pytest.mark.asyncio
async def test_run_streaming_emits_node_status_per_node(runner, manager, mock_pipeline, sample_state):
    """run_streaming() should emit a node_status event after each node completes."""
    # Mock the pipeline to yield two node completions
    mock_events = [
        {"compliance_check": {"status": "checked", "result": {"risk_percentage": 30}}},
        {"post_process": {"status": "checked", "result": {"risk_percentage": 30, "evaluation": {}}}},
    ]
    mock_pipeline.stream.return_value = iter(mock_events)

    await runner.run_streaming("check-001", sample_state)

    # Should have called broadcast_node_status for each node
    assert manager.broadcast_node_status.call_count == 2
    calls = manager.broadcast_node_status.call_args_list

    # First call: compliance_check
    assert calls[0].args[0] == "check-001"
    assert calls[0].args[1] == "compliance_check"
    assert calls[0].args[2] == "completed"
    assert calls[0].args[3] == NODE_DESCRIPTIONS["compliance_check"]

    # Second call: post_process
    assert calls[1].args[0] == "check-001"
    assert calls[1].args[1] == "post_process"
    assert calls[1].args[2] == "completed"


# ── Test interrupt emission at human_review ───────────────────────────────────


@pytest.mark.asyncio
async def test_run_streaming_emits_interrupt_on_graph_interrupt(runner, manager, mock_pipeline, sample_state):
    """run_streaming() should emit an interrupt event when GraphInterrupt is raised."""
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Interrupt

    # Create a GraphInterrupt with the expected payload
    interrupt_payload = {
        "message": "Compliance check complete. Please review the result.",
        "result": {"risk_percentage": 72},
        "options": ["ok", "edit"],
    }

    # GraphInterrupt carries Interrupt objects
    interrupt_obj = Interrupt(value=interrupt_payload, resumable=True, ns=[])
    exc = GraphInterrupt([interrupt_obj])

    mock_pipeline.stream.side_effect = exc
    result = await runner.run_streaming("check-001", sample_state)

    # Should have called send_interrupt
    manager.send_interrupt.assert_called_once()
    call_args = manager.send_interrupt.call_args
    assert call_args.args[0] == "check-001"
    assert call_args.args[1] == "Compliance check complete. Please review the result."
    assert call_args.args[2] == {"risk_percentage": 72}
    assert call_args.args[3] == ["ok", "edit"]

    # Should return None (interrupted, waiting for human input)
    assert result is None


# ── Test result emission on completion ────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_streaming_emits_result_on_completion(runner, manager, mock_pipeline, sample_state):
    """run_streaming() should emit a result event when pipeline completes."""
    # Simulate pipeline completing with final state update
    sample_state.status = "verified"
    sample_state.result = {"risk_percentage": 25, "high_risk_indicator": []}
    sample_state.iteration = 1

    mock_events = [
        {"finalize": sample_state},
    ]

    mock_pipeline.stream.return_value = iter(mock_events)
    await runner.run_streaming("check-001", sample_state)

    # Should have called send_result
    manager.send_result.assert_called_once()
    call_args = manager.send_result.call_args
    assert call_args.args[0] == "check-001"
    result_data = call_args.args[1]
    assert result_data["status"] == "verified"
    assert result_data["iteration"] == 1


# ── Test error emission on node exception ─────────────────────────────────────


@pytest.mark.asyncio
async def test_run_streaming_emits_error_on_exception(runner, manager, mock_pipeline, sample_state):
    """run_streaming() should emit an error event when a node raises an exception."""
    mock_pipeline.stream.side_effect = RuntimeError("Gemini API rate limit exceeded")
    result = await runner.run_streaming("check-001", sample_state)

    # Should have called send_error
    manager.send_error.assert_called_once()
    call_args = manager.send_error.call_args
    assert call_args.args[0] == "check-001"
    # node_name is "unknown" since we can't determine it from RuntimeError
    assert call_args.args[1] == "unknown"
    assert "rate limit" in call_args.args[2].lower()
    assert call_args.kwargs["can_continue"] is False

    # Should return None (errored)
    assert result is None


@pytest.mark.asyncio
async def test_run_streaming_does_not_crash_on_exception(runner, manager, mock_pipeline, sample_state):
    """run_streaming() should NOT raise even when a node throws an exception."""
    mock_pipeline.stream.side_effect = ValueError("Bad data in node")

    # Should not raise — graceful degradation
    result = await runner.run_streaming("check-001", sample_state)

    assert result is None
    manager.send_error.assert_called_once()


@pytest.mark.asyncio
async def test_run_streaming_extracts_node_name_from_exception_message(runner, manager, mock_pipeline, sample_state):
    """If exception message contains a node name, it should be extracted."""
    mock_pipeline.stream.side_effect = RuntimeError(
        "Error in compliance_check: API timeout"
    )
    await runner.run_streaming("check-001", sample_state)

    call_args = manager.send_error.call_args
    assert call_args.args[1] == "compliance_check"


# ── Test resume after interrupt ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resume_emits_node_status_and_result(runner, manager, mock_pipeline):
    """resume() should emit node_status events and final result."""
    final_state = ComplianceState(
        session_id="test",
        media_type="text",
        input_path="",
        text_input="test",
        market="malaysia",
        platform="tiktok",
        ethnicity="malay",
        age_group="gen_z",
        status="verified",
        iteration=1,
        result={"risk_percentage": 20},
    )

    mock_events = [
        {"human_review": final_state},
        {"finalize": final_state},
    ]

    mock_pipeline.stream.return_value = iter(mock_events)
    result = await runner.resume("check-001", "ok")

    # Should have emitted node_status for each node
    assert manager.broadcast_node_status.call_count == 2
    # Should have emitted result
    manager.send_result.assert_called_once()


@pytest.mark.asyncio
async def test_resume_emits_error_on_exception(runner, manager, mock_pipeline):
    """resume() should emit error if pipeline throws during resume."""
    mock_pipeline.stream.side_effect = RuntimeError("remix_router failed: no API key")
    result = await runner.resume("check-001", "edit")

    manager.send_error.assert_called_once()
    call_args = manager.send_error.call_args
    assert "remix_router" in call_args.args[1]
    assert result is None


# ── Test run_with_human_loop ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_with_human_loop_waits_for_decision(
    manager, mock_pipeline, pending_decisions, decision_store, sample_state
):
    """run_with_human_loop() should wait for human decision after interrupt."""
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Interrupt

    runner = PipelineRunner(
        manager,
        pipeline=mock_pipeline,
        pending_decisions=pending_decisions,
        decision_store=decision_store,
    )

    # First call: raises GraphInterrupt (phase 1)
    interrupt_payload = {
        "message": "Please review.",
        "result": {"risk_percentage": 50},
        "options": ["ok", "edit"],
    }
    interrupt_obj = Interrupt(value=interrupt_payload, resumable=True, ns=[])
    exc = GraphInterrupt([interrupt_obj])

    # Second call: resumes and returns final state (phase 2)
    final_state = ComplianceState(
        session_id="test",
        media_type="text",
        input_path="",
        text_input="test",
        market="malaysia",
        platform="tiktok",
        ethnicity="malay",
        age_group="gen_z",
        status="verified",
        iteration=1,
        result={"risk_percentage": 50},
    )

    call_count = [0]

    def mock_stream_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise exc
        return iter([{"finalize": final_state}])

    mock_pipeline.stream.side_effect = mock_stream_side_effect

    # Simulate the human decision arriving shortly after the interrupt
    async def simulate_human_decision():
        await asyncio.sleep(0.05)
        decision_store["check-abc"] = "ok"
        event = pending_decisions.get("check-abc")
        if event:
            event.set()

    asyncio.create_task(simulate_human_decision())

    result = await runner.run_with_human_loop("check-abc", sample_state, timeout=2.0)

    # Should have sent the interrupt
    manager.send_interrupt.assert_called_once()
    # Should have sent the final result after resume
    manager.send_result.assert_called_once()
    assert result is not None


@pytest.mark.asyncio
async def test_run_with_human_loop_timeout(
    manager, mock_pipeline, pending_decisions, decision_store, sample_state
):
    """run_with_human_loop() should emit error on timeout."""
    from langgraph.errors import GraphInterrupt
    from langgraph.types import Interrupt

    runner = PipelineRunner(
        manager,
        pipeline=mock_pipeline,
        pending_decisions=pending_decisions,
        decision_store=decision_store,
    )

    interrupt_payload = {
        "message": "Please review.",
        "result": {},
        "options": ["ok", "edit"],
    }
    interrupt_obj = Interrupt(value=interrupt_payload, resumable=True, ns=[])
    exc = GraphInterrupt([interrupt_obj])

    mock_pipeline.stream.side_effect = exc

    # Use a very short timeout so the test completes quickly
    result = await runner.run_with_human_loop("check-timeout", sample_state, timeout=0.05)

    # Should have sent interrupt, then error on timeout
    manager.send_interrupt.assert_called_once()
    manager.send_error.assert_called_once()
    call_args = manager.send_error.call_args
    assert call_args.args[1] == "human_review"
    assert "timed out" in call_args.args[2].lower()
    assert result is None

    # pending_decisions should be cleaned up
    assert "check-timeout" not in pending_decisions


@pytest.mark.asyncio
async def test_run_with_human_loop_completes_without_interrupt(
    runner, manager, mock_pipeline, sample_state
):
    """run_with_human_loop() should complete normally if no interrupt occurs."""
    sample_state.status = "verified"
    sample_state.result = {"risk_percentage": 10}
    sample_state.iteration = 1

    mock_pipeline.stream.return_value = iter([{"finalize": sample_state}])

    result = await runner.run_with_human_loop("check-fast", sample_state)

    # No interrupt, just straight to result
    manager.send_interrupt.assert_not_called()
    manager.send_result.assert_called_once()
    assert result is not None


# ── Test helper functions ─────────────────────────────────────────────────────


def test_build_result_payload_includes_required_fields():
    """_build_result_payload should include status, result, iteration, media_type, market."""
    state = ComplianceState(
        session_id="s1",
        media_type="image",
        input_path="/tmp/img.png",
        text_input="",
        market="singapore",
        platform="meta",
        ethnicity="chinese",
        age_group="millennial",
        status="verified",
        iteration=1,
        result={"risk_percentage": 15, "high_risk_indicator": []},
    )
    payload = _build_result_payload(state)

    assert payload["status"] == "verified"
    assert payload["result"] == {"risk_percentage": 15, "high_risk_indicator": []}
    assert payload["iteration"] == 1
    assert payload["media_type"] == "image"
    assert payload["market"] == "singapore"


def test_is_interrupt_exception_true_for_graph_interrupt():
    """_is_interrupt_exception should return True for GraphInterrupt."""
    from langgraph.errors import GraphInterrupt
    exc = GraphInterrupt([])
    assert _is_interrupt_exception(exc) is True


def test_is_interrupt_exception_false_for_other_exceptions():
    """_is_interrupt_exception should return False for non-interrupt exceptions."""
    assert _is_interrupt_exception(RuntimeError("test")) is False
    assert _is_interrupt_exception(ValueError("test")) is False


def test_extract_node_from_exception_finds_node_name():
    """_extract_node_from_exception should find node name in exception message."""
    exc = RuntimeError("Failed in post_process: timeout")
    assert _extract_node_from_exception(exc) == "post_process"


def test_extract_node_from_exception_returns_unknown():
    """_extract_node_from_exception should return 'unknown' when no node found."""
    exc = RuntimeError("Something went wrong")
    assert _extract_node_from_exception(exc) == "unknown"


# ── Test PipelineRunner constructor accepts pending_decisions/decision_store ──


def test_pipeline_runner_accepts_decision_dicts(manager, mock_pipeline):
    """PipelineRunner should accept pending_decisions and decision_store args."""
    pd = {}
    ds = {}
    runner = PipelineRunner(manager, pipeline=mock_pipeline, pending_decisions=pd, decision_store=ds)
    assert runner.pending_decisions is pd
    assert runner.decision_store is ds


def test_pipeline_runner_defaults_empty_dicts(manager, mock_pipeline):
    """PipelineRunner should default to empty dicts if not provided."""
    runner = PipelineRunner(manager, pipeline=mock_pipeline)
    assert runner.pending_decisions == {}
    assert runner.decision_store == {}
