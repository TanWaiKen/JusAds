"""
test_validators.py
──────────────────
Unit tests for file size, user quota, and Supabase storage warning validators.

Tests cover:
- File size exactly at 100 MB boundary (accepted)
- File size 1 byte over 100 MB (rejected with HTTP 400)
- Small and large file acceptance/rejection
- User quota enforcement with mocked S3 usage
- Supabase storage warning logging

Requirements: 6.5, 6.6, 6.7
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from agent.validators import (
    MAX_FILE_SIZE_BYTES,
    MAX_USER_QUOTA_BYTES,
    SUPABASE_WARNING_THRESHOLD_BYTES,
    check_supabase_storage_warning,
    validate_file_size,
    validate_user_quota,
)


# ── validate_file_size tests ──────────────────────────────────────────────────


class TestValidateFileSize:
    """Tests for validate_file_size function."""

    def test_accepts_zero_bytes(self):
        """Zero-byte file should be accepted."""
        validate_file_size(0)  # No exception raised

    def test_accepts_small_file(self):
        """A small file (1 KB) should be accepted."""
        validate_file_size(1024)  # No exception

    def test_accepts_file_at_exact_limit(self):
        """A file of exactly 100 MB (104,857,600 bytes) should be accepted."""
        validate_file_size(MAX_FILE_SIZE_BYTES)  # No exception

    def test_rejects_file_one_byte_over_limit(self):
        """A file 1 byte over 100 MB should be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_size(MAX_FILE_SIZE_BYTES + 1)
        assert exc_info.value.status_code == 400
        assert "100 MB" in exc_info.value.detail

    def test_rejects_large_file(self):
        """A file of 200 MB should be rejected with HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_size(200 * 1024 * 1024)
        assert exc_info.value.status_code == 400

    def test_accepts_file_one_byte_under_limit(self):
        """A file 1 byte under 100 MB should be accepted."""
        validate_file_size(MAX_FILE_SIZE_BYTES - 1)  # No exception


# ── validate_user_quota tests ─────────────────────────────────────────────────


class TestValidateUserQuota:
    """Tests for validate_user_quota function."""

    def _make_s3_client(self, current_usage: int) -> MagicMock:
        """Create a mock S3MediaClient that returns a fixed usage."""
        mock_client = MagicMock()
        mock_client.get_user_storage_usage.return_value = current_usage
        return mock_client

    def test_accepts_upload_within_quota(self):
        """Upload that fits within quota should be accepted."""
        s3_client = self._make_s3_client(current_usage=1_000_000_000)  # 1 GB used
        validate_user_quota("testuser", 1_000_000, s3_client)  # 1 MB upload — no exception

    def test_rejects_upload_exceeding_quota(self):
        """Upload that would push over 5 GB should be rejected with HTTP 400."""
        # User already at 4.9 GB, trying to upload 200 MB
        current_usage = int(4.9 * 1024**3)
        file_size = 200 * 1024 * 1024
        s3_client = self._make_s3_client(current_usage=current_usage)

        with pytest.raises(HTTPException) as exc_info:
            validate_user_quota("testuser", file_size, s3_client)
        assert exc_info.value.status_code == 400
        assert "quota exceeded" in exc_info.value.detail.lower()

    def test_accepts_upload_exactly_at_quota(self):
        """Upload that brings usage exactly to 5 GB should be accepted."""
        # current_usage + file_size == MAX_USER_QUOTA_BYTES exactly
        current_usage = MAX_USER_QUOTA_BYTES - 1_000_000
        file_size = 1_000_000
        s3_client = self._make_s3_client(current_usage=current_usage)
        validate_user_quota("testuser", file_size, s3_client)  # No exception

    def test_rejects_upload_one_byte_over_quota(self):
        """Upload 1 byte over quota should be rejected."""
        current_usage = MAX_USER_QUOTA_BYTES - 999_999
        file_size = 1_000_000  # 1 byte over when combined
        s3_client = self._make_s3_client(current_usage=current_usage)

        with pytest.raises(HTTPException) as exc_info:
            validate_user_quota("testuser", file_size, s3_client)
        assert exc_info.value.status_code == 400

    def test_accepts_upload_when_no_existing_usage(self):
        """User with no existing files should accept any file under 5 GB."""
        s3_client = self._make_s3_client(current_usage=0)
        validate_user_quota("newuser", 1_000_000_000, s3_client)  # 1 GB — no exception

    def test_rejects_single_file_exceeding_total_quota(self):
        """Single file larger than 5 GB should be rejected even for new user."""
        s3_client = self._make_s3_client(current_usage=0)
        with pytest.raises(HTTPException) as exc_info:
            validate_user_quota("newuser", MAX_USER_QUOTA_BYTES + 1, s3_client)
        assert exc_info.value.status_code == 400

    def test_calls_s3_client_with_correct_username(self):
        """Should query S3 usage with the provided username."""
        s3_client = self._make_s3_client(current_usage=0)
        validate_user_quota("specific_user", 100, s3_client)
        s3_client.get_user_storage_usage.assert_called_once_with("specific_user")


# ── check_supabase_storage_warning tests ──────────────────────────────────────


class TestCheckSupabaseStorageWarning:
    """Tests for check_supabase_storage_warning function."""

    def test_logs_warning_when_above_threshold(self, caplog):
        """Should log a warning when usage exceeds 400 MB."""
        usage = SUPABASE_WARNING_THRESHOLD_BYTES + 1
        with caplog.at_level(logging.WARNING, logger="agent.validators"):
            check_supabase_storage_warning(usage)
        assert "threshold" in caplog.text.lower() or "80%" in caplog.text

    def test_no_warning_when_below_threshold(self, caplog):
        """Should not log when usage is below 400 MB."""
        usage = SUPABASE_WARNING_THRESHOLD_BYTES - 1
        with caplog.at_level(logging.WARNING, logger="agent.validators"):
            check_supabase_storage_warning(usage)
        assert caplog.text == ""

    def test_no_warning_at_exactly_threshold(self, caplog):
        """Should not log when usage is exactly at 400 MB (only exceeding triggers)."""
        usage = SUPABASE_WARNING_THRESHOLD_BYTES
        with caplog.at_level(logging.WARNING, logger="agent.validators"):
            check_supabase_storage_warning(usage)
        assert caplog.text == ""

    def test_logs_warning_for_very_high_usage(self, caplog):
        """Should log warning for usage near 500 MB."""
        usage = 490 * 1024 * 1024  # 490 MB
        with caplog.at_level(logging.WARNING, logger="agent.validators"):
            check_supabase_storage_warning(usage)
        assert len(caplog.records) == 1
