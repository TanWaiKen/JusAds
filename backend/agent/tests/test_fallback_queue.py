"""
test_fallback_queue.py
──────────────────────
Unit tests for the FallbackQueue class.

Tests cover:
- Local fallback file creation for Supabase writes
- S3 upload queueing
- Background retry processing with success and exhaustion scenarios
- CRITICAL logging on retry exhaustion
- Fallback file retention after exhaustion
"""

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.fallback_queue import FallbackQueue, SupabaseQueueItem, S3QueueItem


@pytest.fixture
def tmp_fallback_dir(tmp_path):
    """Provide a temporary directory for fallback files."""
    return tmp_path / "fallback"


@pytest.fixture
def queue(tmp_fallback_dir):
    """Create a FallbackQueue with a temporary fallback directory."""
    return FallbackQueue(fallback_dir=tmp_fallback_dir)


class TestQueueSupabaseWrite:
    """Tests for queue_supabase_write."""

    def test_creates_fallback_directory(self, tmp_fallback_dir):
        """Fallback directory is created if it does not exist."""
        assert not tmp_fallback_dir.exists()
        queue = FallbackQueue(fallback_dir=tmp_fallback_dir)
        assert tmp_fallback_dir.exists()

    def test_stores_record_as_json_file(self, queue, tmp_fallback_dir):
        """Record is persisted to disk as a JSON file."""
        record = {"check_id": "chk_001", "status": "checked", "risk_percentage": 72}
        queue.queue_supabase_write("chk_001", record)

        fallback_path = tmp_fallback_dir / "chk_001.json"
        assert fallback_path.exists()

        with open(fallback_path, "r") as f:
            stored = json.load(f)
        assert stored == record

    def test_adds_item_to_supabase_queue(self, queue):
        """Item is added to the in-memory Supabase retry queue."""
        record = {"check_id": "chk_002", "status": "pending"}
        queue.queue_supabase_write("chk_002", record)

        assert len(queue.supabase_queue) == 1
        assert queue.supabase_queue[0].check_id == "chk_002"
        assert queue.supabase_queue[0].record == record
        assert queue.supabase_queue[0].attempts == 0
        assert queue.supabase_queue[0].max_attempts == 5
        assert queue.supabase_queue[0].retry_interval == 60.0

    def test_multiple_queued_items(self, queue):
        """Multiple items can be queued."""
        queue.queue_supabase_write("chk_a", {"check_id": "chk_a"})
        queue.queue_supabase_write("chk_b", {"check_id": "chk_b"})

        assert len(queue.supabase_queue) == 2
        assert queue.pending_count == 2


class TestQueueS3Upload:
    """Tests for queue_s3_upload."""

    def test_adds_item_to_s3_queue(self, queue):
        """Item is added to the in-memory S3 retry queue."""
        queue.queue_s3_upload("/tmp/file.mp4", "uploads/user/proj/chk/file.mp4")

        assert len(queue.s3_queue) == 1
        assert queue.s3_queue[0].local_path == "/tmp/file.mp4"
        assert queue.s3_queue[0].s3_key == "uploads/user/proj/chk/file.mp4"
        assert queue.s3_queue[0].attempts == 0
        assert queue.s3_queue[0].max_attempts == 3
        assert queue.s3_queue[0].retry_interval == 30.0

    def test_pending_count_includes_s3_items(self, queue):
        """pending_count reflects both queues."""
        queue.queue_supabase_write("chk_1", {"check_id": "chk_1"})
        queue.queue_s3_upload("/tmp/a.mp4", "uploads/u/p/c/a.mp4")

        assert queue.pending_count == 2


class TestProcessQueue:
    """Tests for the async process_queue background task."""

    @pytest.mark.asyncio
    async def test_supabase_retry_success(self, tmp_fallback_dir):
        """Successful Supabase retry removes item from queue and deletes fallback file."""
        mock_supabase = MagicMock()
        mock_supabase.health_check.return_value = True
        mock_supabase.insert_check.return_value = True

        queue = FallbackQueue(
            fallback_dir=tmp_fallback_dir, supabase_client=mock_supabase
        )
        record = {"check_id": "chk_ok", "status": "checked", "risk_percentage": 55}
        queue.queue_supabase_write("chk_ok", record)

        # Set last_attempt to 0 and retry_interval to 0 so retry fires immediately
        queue.supabase_queue[0].last_attempt = 0
        queue.supabase_queue[0].retry_interval = 0
        queue.supabase_queue[0].max_attempts = 1

        await asyncio.wait_for(queue.process_queue(), timeout=5.0)

        assert len(queue.supabase_queue) == 0
        assert not (tmp_fallback_dir / "chk_ok.json").exists()

    @pytest.mark.asyncio
    async def test_supabase_retry_exhaustion_logs_critical(
        self, tmp_fallback_dir, caplog
    ):
        """Exhausted retries log CRITICAL and retain fallback file."""
        mock_supabase = MagicMock()
        mock_supabase.health_check.return_value = False

        queue = FallbackQueue(
            fallback_dir=tmp_fallback_dir, supabase_client=mock_supabase
        )
        record = {"check_id": "chk_fail", "status": "pending"}
        queue.queue_supabase_write("chk_fail", record)

        # Set retry interval to 0 and max_attempts to 1 for fast test
        queue.supabase_queue[0].retry_interval = 0
        queue.supabase_queue[0].max_attempts = 1

        with caplog.at_level(logging.CRITICAL, logger="agent.fallback_queue"):
            await asyncio.wait_for(queue.process_queue(), timeout=5.0)

        assert len(queue.supabase_queue) == 0
        # Fallback file should be retained
        assert (tmp_fallback_dir / "chk_fail.json").exists()
        # CRITICAL log should mention the check_id
        assert any("chk_fail" in r.message for r in caplog.records if r.levelno == logging.CRITICAL)

    @pytest.mark.asyncio
    async def test_s3_retry_success(self, tmp_fallback_dir, tmp_path):
        """Successful S3 retry removes item from queue."""
        mock_s3 = MagicMock()
        mock_s3.upload_file.return_value = "uploads/u/p/c/file.mp4"

        # Create a temp file to simulate the local file
        local_file = tmp_path / "file.mp4"
        local_file.write_bytes(b"fake video content")

        queue = FallbackQueue(fallback_dir=tmp_fallback_dir, s3_client=mock_s3)
        queue.queue_s3_upload(str(local_file), "uploads/u/p/c/file.mp4")

        queue.s3_queue[0].retry_interval = 0
        queue.s3_queue[0].max_attempts = 1

        await asyncio.wait_for(queue.process_queue(), timeout=5.0)

        assert len(queue.s3_queue) == 0
        mock_s3.upload_file.assert_called_once_with(
            str(local_file), "uploads/u/p/c/file.mp4"
        )

    @pytest.mark.asyncio
    async def test_s3_retry_exhaustion_logs_critical(
        self, tmp_fallback_dir, tmp_path, caplog
    ):
        """Exhausted S3 retries log CRITICAL and retain local file."""
        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = Exception("S3 connection refused")

        local_file = tmp_path / "important.mp4"
        local_file.write_bytes(b"important content")

        queue = FallbackQueue(fallback_dir=tmp_fallback_dir, s3_client=mock_s3)
        queue.queue_s3_upload(str(local_file), "uploads/u/p/c/important.mp4")

        queue.s3_queue[0].retry_interval = 0
        queue.s3_queue[0].max_attempts = 1

        with caplog.at_level(logging.CRITICAL, logger="agent.fallback_queue"):
            await asyncio.wait_for(queue.process_queue(), timeout=5.0)

        assert len(queue.s3_queue) == 0
        # Local file should still exist
        assert local_file.exists()
        # CRITICAL log should be present
        assert any(
            "important.mp4" in r.message
            for r in caplog.records
            if r.levelno == logging.CRITICAL
        )

    @pytest.mark.asyncio
    async def test_empty_queue_exits_immediately(self, tmp_fallback_dir):
        """process_queue exits immediately when both queues are empty."""
        queue = FallbackQueue(fallback_dir=tmp_fallback_dir)
        # Should not hang — exits immediately
        await asyncio.wait_for(queue.process_queue(), timeout=2.0)
        assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_s3_retry_skipped_when_file_missing(
        self, tmp_fallback_dir, caplog
    ):
        """S3 retry is skipped (fails) when local file no longer exists."""
        mock_s3 = MagicMock()

        queue = FallbackQueue(fallback_dir=tmp_fallback_dir, s3_client=mock_s3)
        queue.queue_s3_upload("/nonexistent/path/file.mp4", "uploads/u/p/c/file.mp4")

        queue.s3_queue[0].retry_interval = 0
        queue.s3_queue[0].max_attempts = 1

        with caplog.at_level(logging.CRITICAL, logger="agent.fallback_queue"):
            await asyncio.wait_for(queue.process_queue(), timeout=5.0)

        # Upload should never have been attempted
        mock_s3.upload_file.assert_not_called()


class TestStopMethod:
    """Tests for the stop() method."""

    def test_stop_sets_running_false(self, queue):
        """stop() sets _running to False."""
        queue._running = True
        queue.stop()
        assert queue._running is False
