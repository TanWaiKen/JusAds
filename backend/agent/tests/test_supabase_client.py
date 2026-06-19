"""
test_supabase_client.py
───────────────────────
Unit tests for the SupabaseComplianceStore client.

Tests use mocked Supabase client to verify correct method calls,
pagination logic, and error handling without requiring a live DB connection.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from agent.models import CheckRecord, HistoryResponse


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_supabase_client():
    """Create a mocked Supabase client."""
    with patch("agent.supabase_client.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def store(mock_supabase_client):
    """Create a SupabaseComplianceStore with mocked client."""
    from agent.supabase_client import SupabaseComplianceStore

    store = SupabaseComplianceStore(url="https://test.supabase.co", key="test-key")
    return store


@pytest.fixture
def sample_check_record():
    """Create a sample CheckRecord for testing."""
    return CheckRecord(
        check_id="chk_001",
        user_id="user_123",
        project_id=uuid.uuid4(),
        media_type="image",
        market="malaysia",
        ethnicity="malay",
        age_group="gen_z",
        risk_percentage=72.5,
        risk_band="high",
        confidence=85.0,
        status="checked",
        result_json={"evaluation": {"compliant": False}},
        s3_upload_key="uploads/user_123/proj_1/chk_001/ad.png",
    )


# ── Test insert_check ─────────────────────────────────────────────────────────


def test_insert_check_success(store, mock_supabase_client, sample_check_record):
    """insert_check should call table.insert with serialized record data."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"check_id": "chk_001"}])

    result = store.insert_check(sample_check_record)

    assert result is True
    mock_supabase_client.table.assert_called_with("compliance_checks")
    mock_table.insert.assert_called_once()

    # Verify the data passed has string project_id and ISO timestamps
    insert_data = mock_table.insert.call_args[0][0]
    assert isinstance(insert_data["project_id"], str)
    assert isinstance(insert_data["created_at"], str)
    assert isinstance(insert_data["updated_at"], str)


def test_insert_check_failure(store, mock_supabase_client, sample_check_record):
    """insert_check should return False when an exception occurs."""
    mock_supabase_client.table.side_effect = Exception("Connection refused")

    result = store.insert_check(sample_check_record)

    assert result is False


# ── Test update_check_status ──────────────────────────────────────────────────


def test_update_check_status_success(store, mock_supabase_client):
    """update_check_status should call table.update with status and fields."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"check_id": "chk_001"}])

    result = store.update_check_status(
        "chk_001", "remediated", s3_remix_key="remixed/user/proj/chk/out.png"
    )

    assert result is True
    mock_supabase_client.table.assert_called_with("compliance_checks")
    mock_table.update.assert_called_once()

    update_data = mock_table.update.call_args[0][0]
    assert update_data["status"] == "remediated"
    assert update_data["s3_remix_key"] == "remixed/user/proj/chk/out.png"
    assert "updated_at" in update_data

    mock_table.eq.assert_called_with("check_id", "chk_001")


def test_update_check_status_failure(store, mock_supabase_client):
    """update_check_status should return False on exception."""
    mock_supabase_client.table.side_effect = Exception("Timeout")

    result = store.update_check_status("chk_001", "verified")

    assert result is False


# ── Test get_history ──────────────────────────────────────────────────────────


def test_get_history_returns_paginated_results(store, mock_supabase_client):
    """get_history should return a HistoryResponse with correct pagination."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table

    # Mock count query
    mock_count_chain = MagicMock()
    mock_table.select.return_value = mock_count_chain
    mock_count_chain.eq.return_value = mock_count_chain
    mock_count_chain.order.return_value = mock_count_chain
    mock_count_chain.range.return_value = mock_count_chain

    count_response = MagicMock()
    count_response.count = 45
    count_response.data = [
        {
            "check_id": "chk_001",
            "user_id": "user_123",
            "project_id": str(uuid.uuid4()),
            "media_type": "image",
            "market": "malaysia",
            "ethnicity": "malay",
            "age_group": "gen_z",
            "risk_percentage": 72.5,
            "risk_band": "high",
            "confidence": 85.0,
            "status": "checked",
            "created_at": "2024-01-15T10:00:00+00:00",
            "updated_at": "2024-01-15T10:00:00+00:00",
        }
    ]
    mock_count_chain.execute.return_value = count_response

    result = store.get_history("user_123", page=2, page_size=10)

    assert isinstance(result, HistoryResponse)
    assert result.total == 45
    assert result.page == 2
    assert result.page_size == 10
    assert len(result.records) == 1


def test_get_history_clamps_page_size_max(store, mock_supabase_client):
    """get_history should clamp page_size to 100 maximum."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table

    mock_chain = MagicMock()
    mock_table.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.order.return_value = mock_chain
    mock_chain.range.return_value = mock_chain

    response = MagicMock()
    response.count = 0
    response.data = []
    mock_chain.execute.return_value = response

    result = store.get_history("user_123", page=1, page_size=200)

    assert result.page_size == 100


def test_get_history_clamps_page_size_min(store, mock_supabase_client):
    """get_history should clamp page_size to minimum 1."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table

    mock_chain = MagicMock()
    mock_table.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.order.return_value = mock_chain
    mock_chain.range.return_value = mock_chain

    response = MagicMock()
    response.count = 0
    response.data = []
    mock_chain.execute.return_value = response

    result = store.get_history("user_123", page=1, page_size=0)

    assert result.page_size == 1


def test_get_history_clamps_page_min(store, mock_supabase_client):
    """get_history should clamp page to minimum 1."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table

    mock_chain = MagicMock()
    mock_table.select.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.order.return_value = mock_chain
    mock_chain.range.return_value = mock_chain

    response = MagicMock()
    response.count = 0
    response.data = []
    mock_chain.execute.return_value = response

    result = store.get_history("user_123", page=-5, page_size=20)

    assert result.page == 1


def test_get_history_failure_returns_empty(store, mock_supabase_client):
    """get_history should return empty HistoryResponse on exception."""
    mock_supabase_client.table.side_effect = Exception("Connection error")

    result = store.get_history("user_123")

    assert isinstance(result, HistoryResponse)
    assert result.records == []
    assert result.total == 0


# ── Test insert_violations ────────────────────────────────────────────────────


def test_insert_violations_success(store, mock_supabase_client):
    """insert_violations should bulk insert all violations."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    violations = [
        {
            "violation_index": 0,
            "type": "cultural_sensitivity",
            "severity": "high",
            "description": "Inappropriate imagery",
            "start_time": 1.5,
            "end_time": 3.2,
        },
        {
            "violation_index": 1,
            "type": "misleading_claim",
            "severity": "medium",
            "description": "Unsubstantiated health claim",
        },
    ]

    result = store.insert_violations("chk_001", violations)

    assert result is True
    mock_supabase_client.table.assert_called_with("violations")
    mock_table.insert.assert_called_once()

    rows = mock_table.insert.call_args[0][0]
    assert len(rows) == 2
    assert rows[0]["check_id"] == "chk_001"
    assert rows[0]["violation_index"] == 0
    assert rows[1]["violation_index"] == 1


def test_insert_violations_empty_list(store, mock_supabase_client):
    """insert_violations should return True for an empty list without calling DB."""
    result = store.insert_violations("chk_001", [])

    assert result is True
    mock_supabase_client.table.assert_not_called()


def test_insert_violations_failure(store, mock_supabase_client):
    """insert_violations should return False on exception."""
    mock_supabase_client.table.side_effect = Exception("DB error")

    result = store.insert_violations("chk_001", [{"violation_index": 0, "type": "x", "severity": "low"}])

    assert result is False


# ── Test health_check ─────────────────────────────────────────────────────────


def test_health_check_success(store, mock_supabase_client):
    """health_check should return True when the query succeeds."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    result = store.health_check()

    assert result is True


def test_health_check_failure(store, mock_supabase_client):
    """health_check should return False when an exception occurs."""
    mock_supabase_client.table.side_effect = Exception("Connection refused")

    result = store.health_check()

    assert result is False


# ── Test initialization ───────────────────────────────────────────────────────


@patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": ""})
def test_init_raises_without_url():
    """SupabaseComplianceStore should raise ValueError without URL."""
    from agent.supabase_client import SupabaseComplianceStore

    with pytest.raises(ValueError, match="Supabase URL and key are required"):
        SupabaseComplianceStore(url="", key="some-key")


@patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": ""})
def test_init_raises_without_key():
    """SupabaseComplianceStore should raise ValueError without key."""
    from agent.supabase_client import SupabaseComplianceStore

    with pytest.raises(ValueError, match="Supabase URL and key are required"):
        SupabaseComplianceStore(url="https://test.supabase.co", key="")


# ── Test create_task ──────────────────────────────────────────────────────────


def test_create_task_success(store, mock_supabase_client):
    """create_task should insert a row and return it with id as string."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[{
            "id": uuid.UUID("12345678-1234-1234-1234-123456789abc"),
            "project_id": "proj-001",
            "type": "generation",
            "status": "pending",
            "summary": "New generation task",
            "pipeline_state": {"nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}},
        }]
    )

    result = store.create_task(
        project_id="proj-001",
        task_type="generation",
        status="pending",
        summary="New generation task",
        pipeline_state={"nodes": [], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}},
    )

    assert result["id"] == "12345678-1234-1234-1234-123456789abc"
    assert result["type"] == "generation"
    mock_supabase_client.table.assert_called_with("tasks")
    mock_table.insert.assert_called_once()

    insert_data = mock_table.insert.call_args[0][0]
    assert insert_data["project_id"] == "proj-001"
    assert insert_data["type"] == "generation"
    assert insert_data["status"] == "pending"
    assert "pipeline_state" in insert_data


def test_create_task_compliance_with_reference(store, mock_supabase_client):
    """create_task for compliance should include reference_id."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[{
            "id": uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            "project_id": "proj-002",
            "type": "compliance",
            "status": "checked",
            "summary": "Compliance check",
            "reference_id": "chk_999",
        }]
    )

    result = store.create_task(
        project_id="proj-002",
        task_type="compliance",
        status="checked",
        summary="Compliance check",
        reference_id="chk_999",
    )

    assert result["id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    insert_data = mock_table.insert.call_args[0][0]
    assert insert_data["reference_id"] == "chk_999"
    assert "pipeline_state" not in insert_data


def test_create_task_no_data_raises(store, mock_supabase_client):
    """create_task should raise RuntimeError when Supabase returns no data."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    with pytest.raises(RuntimeError, match="Supabase insert returned no data"):
        store.create_task("proj-001", "generation", "pending", "Test task")


# ── Test list_tasks ───────────────────────────────────────────────────────────


def test_list_tasks_success(store, mock_supabase_client):
    """list_tasks should return tasks ordered by created_at descending."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[
            {"id": uuid.UUID("11111111-1111-1111-1111-111111111111"), "type": "compliance", "status": "checked"},
            {"id": uuid.UUID("22222222-2222-2222-2222-222222222222"), "type": "generation", "status": "pending"},
        ]
    )

    result = store.list_tasks("proj-001")

    assert len(result) == 2
    assert result[0]["id"] == "11111111-1111-1111-1111-111111111111"
    assert result[1]["id"] == "22222222-2222-2222-2222-222222222222"
    mock_table.order.assert_called_with("created_at", desc=True)


def test_list_tasks_empty(store, mock_supabase_client):
    """list_tasks should return empty list for a project with no tasks."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    result = store.list_tasks("proj-empty")

    assert result == []


def test_list_tasks_failure(store, mock_supabase_client):
    """list_tasks should return empty list on exception."""
    mock_supabase_client.table.side_effect = Exception("DB error")

    result = store.list_tasks("proj-001")

    assert result == []


# ── Test get_task_detail ──────────────────────────────────────────────────────


def test_get_task_detail_generation(store, mock_supabase_client):
    """get_task_detail for generation tasks should include pipeline_state."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table

    pipeline = {"nodes": [{"id": "n1"}], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}}
    mock_table.execute.return_value = MagicMock(
        data=[{
            "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
            "project_id": "proj-001",
            "type": "generation",
            "status": "running",
            "pipeline_state": pipeline,
            "reference_id": None,
        }]
    )

    result = store.get_task_detail("proj-001", "33333333-3333-3333-3333-333333333333")

    assert result is not None
    assert result["type"] == "generation"
    assert result["pipeline_state"] == pipeline
    assert "compliance" not in result


def test_get_task_detail_compliance_with_join(store, mock_supabase_client):
    """get_task_detail for compliance tasks should join checks and violations."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table

    # First call: tasks table
    task_response = MagicMock(
        data=[{
            "id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
            "project_id": "proj-002",
            "type": "compliance",
            "status": "checked",
            "reference_id": "chk_100",
            "pipeline_state": None,
        }]
    )
    # Second call: compliance_checks table
    check_response = MagicMock(
        data=[{
            "risk_percentage": 72.5,
            "status": "checked",
            "market": "malaysia",
            "s3_remix_key": "remixed/key.png",
            "check_id": "chk_100",
        }]
    )
    # Third call: violations table
    violations_response = MagicMock(
        data=[
            {"violation_index": 0, "type": "cultural", "severity": "high", "description": "Issue 1"},
        ]
    )

    mock_table.execute.side_effect = [task_response, check_response, violations_response]

    result = store.get_task_detail("proj-002", "44444444-4444-4444-4444-444444444444")

    assert result is not None
    assert result["type"] == "compliance"
    assert "compliance" in result
    assert result["compliance"]["risk_percentage"] == 72.5
    assert result["compliance"]["market"] == "malaysia"
    assert result["compliance"]["s3_remix_key"] == "remixed/key.png"
    assert len(result["compliance"]["violations"]) == 1


def test_get_task_detail_not_found(store, mock_supabase_client):
    """get_task_detail should return None when task not found."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    result = store.get_task_detail("proj-001", "nonexistent-id")

    assert result is None


def test_get_task_detail_failure(store, mock_supabase_client):
    """get_task_detail should return None on exception."""
    mock_supabase_client.table.side_effect = Exception("Connection error")

    result = store.get_task_detail("proj-001", "some-id")

    assert result is None


# ── Test update_task_pipeline ─────────────────────────────────────────────────


def test_update_task_pipeline_success(store, mock_supabase_client):
    """update_task_pipeline should update status and pipeline_state."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "task-1"}])

    pipeline = {"nodes": [{"id": "n1"}], "edges": [], "viewport": {"panX": 0, "panY": 0, "zoom": 1}}
    result = store.update_task_pipeline("proj-001", "task-1", "completed", pipeline)

    assert result is True
    mock_supabase_client.table.assert_called_with("tasks")
    mock_table.update.assert_called_once()

    update_data = mock_table.update.call_args[0][0]
    assert update_data["status"] == "completed"
    assert update_data["pipeline_state"] == pipeline
    assert "updated_at" in update_data


def test_update_task_pipeline_failure(store, mock_supabase_client):
    """update_task_pipeline should return False on exception."""
    mock_supabase_client.table.side_effect = Exception("Timeout")

    result = store.update_task_pipeline("proj-001", "task-1", "running", {})

    assert result is False


# ── Test update_project_name ──────────────────────────────────────────────────


def test_update_project_name_success(store, mock_supabase_client):
    """update_project_name should update name and return the updated row."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[{
            "id": uuid.UUID("55555555-5555-5555-5555-555555555555"),
            "name": "Updated Name",
            "media_type": "compliance",
        }]
    )

    result = store.update_project_name("55555555-5555-5555-5555-555555555555", "  Updated Name  ")

    assert result["id"] == "55555555-5555-5555-5555-555555555555"
    assert result["name"] == "Updated Name"
    mock_supabase_client.table.assert_called_with("projects")

    update_data = mock_table.update.call_args[0][0]
    assert update_data["name"] == "Updated Name"  # trimmed
    assert "updated_at" in update_data


def test_update_project_name_no_data_raises(store, mock_supabase_client):
    """update_project_name should raise RuntimeError when Supabase returns no data."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    with pytest.raises(RuntimeError, match="Supabase update returned no data"):
        store.update_project_name("proj-001", "New Name")


def test_update_project_name_failure(store, mock_supabase_client):
    """update_project_name should raise on unexpected exception."""
    mock_supabase_client.table.side_effect = Exception("Connection error")

    with pytest.raises(Exception, match="Connection error"):
        store.update_project_name("proj-001", "New Name")
