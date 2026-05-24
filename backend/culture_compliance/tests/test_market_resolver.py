"""Unit tests for market resolution logic.

Tests case-insensitive matching, default market fallback, unsupported market
rejection, and collection name mapping.
"""

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step1_routing import (
    COLLECTION_CONFIG,
    get_collection_name,
    market_resolution,
    resolve_market,
)


# --- resolve_market tests ---


class TestResolveMarket:
    """Tests for the resolve_market function."""

    def test_malaysia_lowercase(self):
        assert resolve_market("malaysia") == Market.MALAYSIA

    def test_singapore_lowercase(self):
        assert resolve_market("singapore") == Market.SINGAPORE

    def test_malaysia_mixed_case(self):
        assert resolve_market("Malaysia") == Market.MALAYSIA

    def test_singapore_mixed_case(self):
        assert resolve_market("Singapore") == Market.SINGAPORE

    def test_malaysia_uppercase(self):
        assert resolve_market("MALAYSIA") == Market.MALAYSIA

    def test_singapore_uppercase(self):
        assert resolve_market("SINGAPORE") == Market.SINGAPORE

    def test_malaysia_random_case(self):
        assert resolve_market("mAlAySiA") == Market.MALAYSIA

    def test_singapore_random_case(self):
        assert resolve_market("sInGaPoRe") == Market.SINGAPORE

    def test_default_when_none(self):
        """Default to Malaysia when no market specified."""
        assert resolve_market(None) == Market.MALAYSIA

    def test_default_when_empty_string(self):
        """Default to Malaysia when empty string provided."""
        assert resolve_market("") == Market.MALAYSIA

    def test_unsupported_market_raises(self):
        """Unsupported market values raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported market"):
            resolve_market("thailand")

    def test_unsupported_market_lists_supported(self):
        """Error message lists supported markets."""
        with pytest.raises(ValueError, match="malaysia.*singapore"):
            resolve_market("japan")

    def test_whitespace_only_defaults(self):
        """Whitespace-only string defaults to Malaysia."""
        assert resolve_market("   ") == Market.MALAYSIA

    def test_market_with_leading_trailing_spaces(self):
        """Leading/trailing spaces are trimmed before matching."""
        assert resolve_market("  malaysia  ") == Market.MALAYSIA
        assert resolve_market("  singapore  ") == Market.SINGAPORE


# --- get_collection_name tests ---


class TestGetCollectionName:
    """Tests for the get_collection_name function."""

    def test_malaysia_collection(self):
        assert get_collection_name(Market.MALAYSIA) == "mcmc-guidelines"

    def test_singapore_collection(self):
        assert get_collection_name(Market.SINGAPORE) == "singapore-imda-asas-guidelines"


# --- market_resolution node tests ---


class TestMarketResolutionNode:
    """Tests for the market_resolution pipeline node."""

    def _make_state(self, market: Market = Market.MALAYSIA) -> PipelineState:
        """Create a minimal PipelineState for testing."""
        submission = ContentSubmission(
            content="Test ad copy for compliance review",
            content_type=ContentType.TEXT,
            market=market,
        )
        return PipelineState(
            submission=submission,
            content_type=submission.content_type,
            market=submission.market,
        )

    def test_malaysia_market_sets_collection(self):
        state = self._make_state(Market.MALAYSIA)
        result = market_resolution(state)
        assert result.market == Market.MALAYSIA
        assert result.guideline_collection == "mcmc-guidelines"
        assert result.errors == []

    def test_singapore_market_sets_collection(self):
        state = self._make_state(Market.SINGAPORE)
        result = market_resolution(state)
        assert result.market == Market.SINGAPORE
        assert result.guideline_collection == "singapore-imda-asas-guidelines"
        assert result.errors == []

    def test_no_errors_on_valid_market(self):
        state = self._make_state(Market.MALAYSIA)
        result = market_resolution(state)
        assert len(result.errors) == 0

    def test_collection_config_has_both_markets(self):
        """COLLECTION_CONFIG covers all Market enum values."""
        for market in Market:
            assert market in COLLECTION_CONFIG
            assert "collection_name" in COLLECTION_CONFIG[market]
            assert "source_authority" in COLLECTION_CONFIG[market]
