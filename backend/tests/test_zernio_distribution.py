import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jusads_generation.distribution import (
    distribute_ad,
    get_ad_analytics,
    AccountNotConfiguredError,
    DistributionError,
)

@patch("jusads_generation.distribution.ZERNIO_ACCOUNT_TIKTOK", "test-tiktok-id")
@patch("jusads_generation.distribution.ZERNIO_ACCOUNT_INSTAGRAM", "test-instagram-id")
def test_resolve_account_id():
    from jusads_generation.distribution import _resolve_account_id
    assert _resolve_account_id("tiktok") == "test-tiktok-id"
    assert _resolve_account_id("instagram") == "test-instagram-id"
    assert _resolve_account_id("unknown") is None

@patch("jusads_generation.distribution.ZERNIO_ACCOUNT_TIKTOK", "test-tiktok-id")
@patch("jusads_generation.distribution.ZERNIO_ACCOUNT_INSTAGRAM", "test-instagram-id")
@patch("jusads_generation.distribution.ZERNIO_API_KEY", "test-api-key")
@patch("jusads_generation.distribution.Zernio")
def test_distribute_ad_success(mock_zernio_class):
    mock_client = MagicMock()
    mock_zernio_class.return_value = mock_client
    
    mock_post_response = {"post": {"_id": "test-post-123"}}
    mock_client.posts.create.return_value = mock_post_response

    with patch("jusads_generation.distribution.supabase") as mock_supabase:
        result = distribute_ad(
            ad_id="test-ad-id",
            platform="tiktok",
            media_url="https://s3.amazonaws.com/test-media.mp4",
            media_type="video",
            caption="Test ad caption",
        )
        
        assert result["post_id"] == "test-post-123"
        assert result["status"] == "distributed"
        assert result["platform"] == "tiktok"
        mock_client.posts.create.assert_called_once()

@patch("jusads_generation.distribution.ZERNIO_API_KEY", "")
def test_distribute_ad_missing_key():
    with pytest.raises(DistributionError) as exc:
        distribute_ad(
            ad_id="test-ad-id",
            platform="tiktok",
            media_url="https://s3.amazonaws.com/test-media.mp4",
            media_type="video",
        )
    assert "ZERNIO_API_KEY is not configured" in str(exc.value)

@patch("jusads_generation.distribution.ZERNIO_API_KEY", "test-api-key")
def test_distribute_ad_unconfigured_platform():
    with pytest.raises(AccountNotConfiguredError) as exc:
        distribute_ad(
            ad_id="test-ad-id",
            platform="invalid-platform",
            media_url="https://s3.amazonaws.com/test-media.mp4",
            media_type="video",
        )
    assert "No Zernio account configured" in str(exc.value)

@patch("jusads_generation.distribution.ZERNIO_API_KEY", "")
@patch("jusads_generation.distribution.supabase")
def test_get_ad_analytics_mocked(mock_supabase):
    mock_execute = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute = mock_execute
    mock_execute.return_value.data = [
        {
            "id": "test-ad-id",
            "distribution_platform": "tiktok",
            "distribution_post_id": "test-post-123",
            "media_type": "video",
        }
    ]
    
    result = get_ad_analytics("test-ad-id", "test-project-id")
    
    assert result["status"] == "mocked"
    assert result["platform"] == "tiktok"
    assert "metrics" in result
    assert "chart_data" in result
