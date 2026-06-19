"""
test_s3_client.py
─────────────────
Unit tests for the S3MediaClient and build_s3_key helper.
Uses mocking to avoid real AWS calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.s3_client import S3MediaClient, build_s3_key


# ── build_s3_key tests ────────────────────────────────────────────────────────


class TestBuildS3Key:
    """Tests for the build_s3_key helper function."""

    def test_upload_key_format(self):
        key = build_s3_key("upload", "alice", "proj-1", "chk-abc", "video.mp4")
        assert key == "uploads/alice/proj-1/chk-abc/video.mp4"

    def test_remixed_key_format(self):
        key = build_s3_key("remixed", "bob", "proj-2", "chk-xyz", "remix.wav")
        assert key == "remixed/bob/proj-2/chk-xyz/remix.wav"

    def test_invalid_asset_type_raises(self):
        with pytest.raises(ValueError, match="Invalid asset_type"):
            build_s3_key("clips", "alice", "proj-1", "chk-abc", "file.mp4")

    def test_key_preserves_special_characters_in_filename(self):
        key = build_s3_key("upload", "user1", "p1", "c1", "my file (1).mp4")
        assert key == "uploads/user1/p1/c1/my file (1).mp4"


# ── S3MediaClient tests ──────────────────────────────────────────────────────


class TestS3MediaClient:
    """Tests for the S3MediaClient class using mocked boto3."""

    @patch("agent.s3_client.boto3.client")
    def test_upload_file_returns_key(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        result = client.upload_file("/tmp/video.mp4", "uploads/alice/p1/c1/video.mp4")

        assert result == "uploads/alice/p1/c1/video.mp4"
        mock_s3.upload_file.assert_called_once_with(
            "/tmp/video.mp4", "test-bucket", "uploads/alice/p1/c1/video.mp4"
        )

    @patch("agent.s3_client.boto3.client")
    def test_generate_presigned_url(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/signed"
        mock_boto_client.return_value = mock_s3

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        url = client.generate_presigned_url("uploads/alice/p1/c1/video.mp4", expiry_seconds=7200)

        assert url == "https://s3.example.com/signed"
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "uploads/alice/p1/c1/video.mp4"},
            ExpiresIn=7200,
        )

    @patch("agent.s3_client.boto3.client")
    def test_generate_presigned_url_default_expiry(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/signed"
        mock_boto_client.return_value = mock_s3

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        client.generate_presigned_url("key/path")

        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "key/path"},
            ExpiresIn=3600,
        )

    @patch("agent.s3_client.boto3.client")
    def test_get_user_storage_usage(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        # Simulate paginator responses for uploads/ and remixed/ prefixes
        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = [
            # uploads/alice/ — two objects
            [{"Contents": [{"Size": 1000}, {"Size": 2000}]}],
            # remixed/alice/ — one object
            [{"Contents": [{"Size": 500}]}],
        ]

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        usage = client.get_user_storage_usage("alice")

        assert usage == 3500

    @patch("agent.s3_client.boto3.client")
    def test_get_user_storage_usage_empty(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        # No contents for either prefix
        mock_paginator.paginate.side_effect = [
            [{}],
            [{}],
        ]

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        usage = client.get_user_storage_usage("new_user")

        assert usage == 0

    @patch("agent.s3_client.boto3.client")
    def test_check_quota_within_limit(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = [
            [{"Contents": [{"Size": 1_000_000}]}],  # uploads
            [{}],  # remixed
        ]

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        # 1MB used, trying to upload 1MB more — well within 5GB
        assert client.check_quota("alice", 1_000_000) is True

    @patch("agent.s3_client.boto3.client")
    def test_check_quota_exceeds_limit(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        # Simulate 4.9 GB existing usage
        existing_bytes = int(4.9 * 1024**3)
        mock_paginator.paginate.side_effect = [
            [{"Contents": [{"Size": existing_bytes}]}],  # uploads
            [{}],  # remixed
        ]

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        # Trying to upload 200MB would exceed 5GB
        assert client.check_quota("alice", 200 * 1024**2) is False

    @patch("agent.s3_client.boto3.client")
    def test_check_quota_custom_max(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = [
            [{"Contents": [{"Size": 500}]}],
            [{}],
        ]

        client = S3MediaClient(bucket_name="test-bucket", region="us-east-1")
        # Custom max of 1000 bytes — 500 existing + 600 new = 1100 > 1000
        assert client.check_quota("alice", 600, max_bytes=1000) is False
        # 500 existing + 400 new = 900 ≤ 1000
        mock_paginator.paginate.side_effect = [
            [{"Contents": [{"Size": 500}]}],
            [{}],
        ]
        assert client.check_quota("alice", 400, max_bytes=1000) is True
