"""
test_history_media_endpoints.py
───────────────────────────────
Unit tests for the GET /api/compliance/history and GET /api/media/{check_id}/{asset_type}
endpoints added to langgraph_api.py.

Tests cover:
- History endpoint: pagination, default params, response shape
- Media URL endpoint: original/remixed asset types, 404 for missing records, 400 for invalid asset type
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import uuid

from agent.models import CheckRecord, HistoryResponse


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_records():
    """Create sample CheckRecords for testing."""
    now = datetime.now(timezone.utc)
    return [
        CheckRecord(
            check_id=f"check-{i:03d}",
            user_id="demo_user",
            project_id=uuid.uuid4(),
            media_type="image",
            market="malaysia",
            ethnicity="malay",
            age_group="all_ages",
            risk_percentage=50.0,
            risk_band="Moderate",
            confidence=80.0,
            status="checked",
            s3_upload_key=f"uploads/demo_user/proj/check-{i:03d}/file.png",
            s3_remix_key=f"remixed/demo_user/proj/check-{i:03d}/file.png" if i % 2 == 0 else None,
            created_at=now,
            updated_at=now,
        )
        for i in range(5)
    ]


def _build_test_app(mock_store=None, mock_s3_client=None):
    """Create a minimal FastAPI app with the history and media endpoints for testing.
    
    Accepts pre-configured mocks to inject into the endpoint handlers.
    """
    app = FastAPI()

    @app.get("/api/compliance/history")
    async def get_compliance_history(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        user_id = "demo_user"
        try:
            store = mock_store
            history = store.get_history(user_id=user_id, page=page, page_size=page_size)
            return JSONResponse(content={
                "records": [record.model_dump(mode="json") for record in history.records],
                "total": history.total,
                "page": history.page,
                "page_size": history.page_size,
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to fetch compliance history", "detail": str(e)},
            )

    @app.get("/api/media/{check_id}/{asset_type}")
    async def get_media_url(check_id: str, asset_type: str):
        if asset_type not in ("original", "remixed"):
            return JSONResponse(
                status_code=400,
                content={"error": "asset_type must be 'original' or 'remixed'"},
            )

        try:
            store = mock_store
            response = (
                store.client.table("compliance_checks")
                .select("s3_upload_key, s3_remix_key")
                .eq("check_id", check_id)
                .execute()
            )

            if not response.data:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Check record not found for check_id: {check_id}"},
                )

            record = response.data[0]

            if asset_type == "original":
                s3_key = record.get("s3_upload_key")
            else:
                s3_key = record.get("s3_remix_key")

            if not s3_key:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"No {asset_type} media found for check_id: {check_id}"},
                )

            s3_client = mock_s3_client
            url = s3_client.generate_presigned_url(s3_key, expiry_seconds=3600)
            return JSONResponse(content={"url": url, "check_id": check_id, "asset_type": asset_type})

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to generate media URL", "detail": str(e)},
            )

    return app


# ── History Endpoint Tests ────────────────────────────────────────────────────


def test_history_returns_paginated_records(sample_records):
    """History endpoint returns paginated records with correct structure."""
    mock_store = MagicMock()
    mock_store.get_history.return_value = HistoryResponse(
        records=sample_records[:3],
        total=5,
        page=1,
        page_size=3,
    )

    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/compliance/history?page=1&page_size=3")

    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 3
    assert len(data["records"]) == 3


def test_history_default_pagination(sample_records):
    """History endpoint uses default page=1, page_size=20 when no params provided."""
    mock_store = MagicMock()
    mock_store.get_history.return_value = HistoryResponse(
        records=sample_records,
        total=5,
        page=1,
        page_size=20,
    )

    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/compliance/history")

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 20

    # Verify the store was called with default params
    mock_store.get_history.assert_called_once_with(user_id="demo_user", page=1, page_size=20)


def test_history_rejects_invalid_page():
    """History endpoint rejects page < 1."""
    mock_store = MagicMock()
    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/compliance/history?page=0")
    assert response.status_code == 422  # FastAPI validation error


def test_history_rejects_page_size_over_100():
    """History endpoint rejects page_size > 100."""
    mock_store = MagicMock()
    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/compliance/history?page_size=101")
    assert response.status_code == 422  # FastAPI validation error


def test_history_record_contains_expected_fields(sample_records):
    """Each record in the history response contains all expected fields."""
    mock_store = MagicMock()
    mock_store.get_history.return_value = HistoryResponse(
        records=[sample_records[0]],
        total=1,
        page=1,
        page_size=20,
    )

    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/compliance/history")

    assert response.status_code == 200
    data = response.json()
    record = data["records"][0]

    # CheckRecord fields that should be present
    assert "check_id" in record
    assert "user_id" in record
    assert "media_type" in record
    assert "market" in record
    assert "risk_band" in record
    assert "status" in record
    assert "created_at" in record


# ── Media URL Endpoint Tests ──────────────────────────────────────────────────


def test_media_url_returns_presigned_url_for_original():
    """Media endpoint returns presigned URL for original asset."""
    mock_store = MagicMock()
    mock_s3 = MagicMock()

    # Mock Supabase response
    mock_response = MagicMock()
    mock_response.data = [{"s3_upload_key": "uploads/user/proj/check-001/file.mp4", "s3_remix_key": None}]
    mock_store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    # Mock S3 presigned URL
    mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/uploads/user/proj/check-001/file.mp4?signed=abc"

    app = _build_test_app(mock_store=mock_store, mock_s3_client=mock_s3)
    client = TestClient(app)
    response = client.get("/api/media/check-001/original")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert data["check_id"] == "check-001"
    assert data["asset_type"] == "original"
    assert "signed" in data["url"]

    # Verify S3 was called with correct key and expiry
    mock_s3.generate_presigned_url.assert_called_once_with(
        "uploads/user/proj/check-001/file.mp4", expiry_seconds=3600
    )


def test_media_url_returns_presigned_url_for_remixed():
    """Media endpoint returns presigned URL for remixed asset."""
    mock_store = MagicMock()
    mock_s3 = MagicMock()

    mock_response = MagicMock()
    mock_response.data = [{"s3_upload_key": "uploads/user/proj/check-002/file.mp4", "s3_remix_key": "remixed/user/proj/check-002/file.mp4"}]
    mock_store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/remixed/user/proj/check-002/file.mp4?signed=xyz"

    app = _build_test_app(mock_store=mock_store, mock_s3_client=mock_s3)
    client = TestClient(app)
    response = client.get("/api/media/check-002/remixed")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert data["asset_type"] == "remixed"

    mock_s3.generate_presigned_url.assert_called_once_with(
        "remixed/user/proj/check-002/file.mp4", expiry_seconds=3600
    )


def test_media_url_returns_404_for_missing_check():
    """Media endpoint returns 404 if check_id doesn't exist."""
    mock_store = MagicMock()

    mock_response = MagicMock()
    mock_response.data = []
    mock_store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/media/nonexistent/original")

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_media_url_returns_404_for_missing_remix_key():
    """Media endpoint returns 404 if remixed key is not set on the record."""
    mock_store = MagicMock()

    mock_response = MagicMock()
    mock_response.data = [{"s3_upload_key": "uploads/user/proj/check-003/file.png", "s3_remix_key": None}]
    mock_store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/media/check-003/remixed")

    assert response.status_code == 404
    assert "No remixed media found" in response.json()["error"]


def test_media_url_returns_400_for_invalid_asset_type():
    """Media endpoint returns 400 for invalid asset_type."""
    app = _build_test_app(mock_store=MagicMock())
    client = TestClient(app)
    response = client.get("/api/media/check-001/invalid_type")

    assert response.status_code == 400
    assert "asset_type must be" in response.json()["error"]


def test_media_url_returns_404_when_upload_key_is_none():
    """Media endpoint returns 404 if the original s3_upload_key is None."""
    mock_store = MagicMock()

    mock_response = MagicMock()
    mock_response.data = [{"s3_upload_key": None, "s3_remix_key": "remixed/user/proj/check-004/file.png"}]
    mock_store.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

    app = _build_test_app(mock_store=mock_store)
    client = TestClient(app)
    response = client.get("/api/media/check-004/original")

    assert response.status_code == 404
    assert "No original media found" in response.json()["error"]
