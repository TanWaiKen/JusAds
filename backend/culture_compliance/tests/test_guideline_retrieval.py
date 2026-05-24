"""Unit tests for the guideline retrieval node.

Tests validate that the guideline retrieval node correctly:
- Retrieves guidelines from both regulatory and cultural Qdrant collections
- Stores formatted guidelines in state.retrieved_guidelines
- Labels results as "regulatory" or "cultural"
- Merges results by similarity score descending, takes top 50
- Handles Qdrant unavailability with error response
- Handles embedding failures with error response
- Handles missing guideline_collection in state
- Handles missing unified_content in state
- Builds correct Qdrant payload filters for cultural collection
"""

from unittest.mock import MagicMock, patch, call
from types import SimpleNamespace

import pytest

from culture_compliance.models.schemas import (
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.nodes.step5_guideline_retrieval import (
    guideline_retrieval,
    _build_cultural_filter,
    _format_labeled_results,
)


def _make_state(
    content: str = "Buy our halal-certified product today!",
    market: Market = Market.MALAYSIA,
    collection: str = "mcmc-guidelines",
    unified_content: str = "Buy our halal-certified product today!",
    target_ethnicity: str = "all",
    target_age_group: str = "all_ages",
) -> PipelineState:
    """Helper to create a PipelineState for guideline retrieval testing."""
    submission = ContentSubmission(
        content=content,
        content_type=ContentType.TEXT,
        market=market,
        target_ethnicity=target_ethnicity,
        target_age_group=target_age_group,
    )
    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=market,
        target_ethnicity=target_ethnicity,
        target_age_group=target_age_group,
    )
    state.guideline_collection = collection
    state.unified_content = unified_content
    return state


def _mock_regulatory_results(num_points: int = 3):
    """Create mock Qdrant query results for regulatory collection."""
    points = []
    for i in range(num_points):
        point = SimpleNamespace(
            id=f"reg-{i}",
            score=0.95 - (i * 0.05),
            payload={
                "source": "mcmc_guidelines.csv",
                "row_text": f"guideline text {i}",
                "Category": f"Category {i}",
                "Guideline": f"Guideline content {i} about advertising standards",
            },
        )
        points.append(point)
    return SimpleNamespace(points=points)


def _mock_cultural_results(num_points: int = 2):
    """Create mock Qdrant query results for cultural collection."""
    points = []
    for i in range(num_points):
        point = SimpleNamespace(
            id=f"cult-{i}",
            score=0.90 - (i * 0.05),
            payload={
                "market": "malaysia",
                "ethnicity": "malay",
                "age_group": "all_ages",
                "category": "body_exposure",
                "severity": "high",
                "guideline_text": f"Cultural guideline {i} about modesty standards",
                "source": "cultural_guidelines.csv",
            },
        )
        points.append(point)
    return SimpleNamespace(points=points)


# Keep backward compat alias for tests that use the old name
_mock_qdrant_results = _mock_regulatory_results


class TestGuidelineRetrievalSuccess:
    """Tests for successful guideline retrieval."""

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_retrieves_guidelines_and_stores_in_state(
        self, mock_embed, mock_get_client
    ):
        """Successfully retrieves guidelines and stores formatted string in state."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        # First call: regulatory, second call: cultural
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(3),
            _mock_cultural_results(2),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        assert result.retrieved_guidelines is not None
        assert result.errors == []
        assert "REGULATORY" in result.retrieved_guidelines
        assert "CULTURAL" in result.retrieved_guidelines
        assert result.regulatory_guidelines is not None
        assert result.cultural_guidelines is not None
        assert len(result.guideline_sources) > 0

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_queries_both_collections(self, mock_embed, mock_get_client):
        """Queries both regulatory and cultural collections."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(2),
            _mock_cultural_results(1),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state(collection="singapore-imda-asas-guidelines")
        result = guideline_retrieval(state)

        # Should have been called twice: once for regulatory, once for cultural
        assert mock_client.query_points.call_count == 2
        # First call is regulatory collection
        first_call = mock_client.query_points.call_args_list[0]
        assert first_call.kwargs["collection_name"] == "singapore-imda-asas-guidelines"
        # Second call is cultural collection
        second_call = mock_client.query_points.call_args_list[1]
        assert second_call.kwargs["collection_name"] == "cultural-guidelines"
        assert result.errors == []

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_embeds_unified_content_as_search_query(
        self, mock_embed, mock_get_client
    ):
        """Embeds the unified_content with input_type='search_query'."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(1),
            _mock_cultural_results(0),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state(unified_content="Test ad copy for embedding")
        guideline_retrieval(state)

        mock_embed.assert_called_once_with(
            "Test ad copy for embedding", input_type="search_query"
        )

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_handles_no_results_from_both_collections(self, mock_embed, mock_get_client):
        """Returns appropriate message when both collections return empty."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = [
            SimpleNamespace(points=[]),
            SimpleNamespace(points=[]),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        assert "No relevant regulatory guidelines found." in result.retrieved_guidelines
        assert "No relevant cultural guidelines found." in result.retrieved_guidelines
        assert result.errors == []

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_formats_multiple_guidelines_with_scores(
        self, mock_embed, mock_get_client
    ):
        """Formats multiple guidelines with numbered entries and relevance scores."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(3),
            _mock_cultural_results(2),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        assert "relevance: 0.95" in result.retrieved_guidelines
        assert result.errors == []
        # Should have 5 total guideline sources
        assert len(result.guideline_sources) == 5

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_labels_results_with_source(self, mock_embed, mock_get_client):
        """Labels each result as regulatory or cultural."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(2),
            _mock_cultural_results(2),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        sources = [s["source"] for s in result.guideline_sources]
        assert "regulatory" in sources
        assert "cultural" in sources

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_merges_results_by_score_descending(self, mock_embed, mock_get_client):
        """Merges results from both collections sorted by score descending."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(3),
            _mock_cultural_results(2),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        # Verify scores are in descending order
        scores = [s["score"] for s in result.guideline_sources]
        assert scores == sorted(scores, reverse=True)


class TestGuidelineRetrievalErrors:
    """Tests for error handling in guideline retrieval."""

    def test_error_when_no_collection_specified(self):
        """Returns error when guideline_collection is not set in state."""
        state = _make_state()
        state.guideline_collection = None

        result = guideline_retrieval(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "guideline_retrieval"
        assert result.errors[0]["error_type"] == "validation"
        assert "collection" in result.errors[0]["message"].lower()
        assert result.retrieved_guidelines is None

    def test_error_when_no_unified_content(self):
        """Returns error when unified_content is not set in state."""
        state = _make_state()
        state.unified_content = None

        result = guideline_retrieval(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "guideline_retrieval"
        assert result.errors[0]["error_type"] == "validation"
        assert "content" in result.errors[0]["message"].lower()
        assert result.retrieved_guidelines is None

    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_error_when_embedding_fails(self, mock_embed):
        """Returns service_unavailable error when embedding fails."""
        mock_embed.side_effect = Exception("Bedrock throttling error")

        state = _make_state()
        result = guideline_retrieval(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "guideline_retrieval"
        assert result.errors[0]["error_type"] == "service_unavailable"
        assert "embed" in result.errors[0]["message"].lower()
        assert result.retrieved_guidelines is None

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_error_when_regulatory_qdrant_unavailable(self, mock_embed, mock_get_client):
        """Returns service_unavailable error when regulatory Qdrant query fails."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        # First call (regulatory) fails
        mock_client.query_points.side_effect = ConnectionError(
            "Connection refused"
        )
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        assert len(result.errors) == 1
        assert result.errors[0]["node"] == "guideline_retrieval"
        assert result.errors[0]["error_type"] == "service_unavailable"
        assert "unavailable" in result.errors[0]["message"].lower()
        assert result.retrieved_guidelines is None

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_cultural_failure_is_non_fatal(self, mock_embed, mock_get_client):
        """Cultural collection failure is non-fatal — proceeds with regulatory only."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        # First call (regulatory) succeeds, second call (cultural) fails
        mock_client.query_points.side_effect = [
            _mock_regulatory_results(3),
            ConnectionError("Cultural collection unavailable"),
        ]
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        # Should succeed with regulatory results only
        assert result.errors == []
        assert len(result.warnings) == 1
        assert "cultural" in result.warnings[0]["description"].lower()
        assert result.retrieved_guidelines is not None
        assert "REGULATORY" in result.retrieved_guidelines

    @patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
    @patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
    def test_error_when_qdrant_returns_unexpected_response(
        self, mock_embed, mock_get_client
    ):
        """Returns error when regulatory Qdrant returns an unexpected response."""
        mock_embed.return_value = [0.1] * 1024
        mock_client = MagicMock()
        mock_client.query_points.side_effect = Exception(
            "Unexpected server error"
        )
        mock_get_client.return_value = mock_client

        state = _make_state()
        result = guideline_retrieval(state)

        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "service_unavailable"
        assert result.retrieved_guidelines is None


class TestFormatLabeledResults:
    """Tests for the _format_labeled_results helper function."""

    def test_formats_regulatory_and_cultural_results(self):
        """Formats results from both collections with labels."""
        reg_results = _mock_regulatory_results(2)
        cult_results = _mock_cultural_results(1)

        reg_str, cult_str, combined_str, sources = _format_labeled_results(
            reg_results.points, cult_results.points
        )

        assert "REGULATORY GUIDELINES" in combined_str
        assert "CULTURAL GUIDELINES" in combined_str
        assert len(sources) == 3

    def test_formats_empty_results(self):
        """Returns 'no guidelines' messages for empty results."""
        reg_str, cult_str, combined_str, sources = _format_labeled_results([], [])

        assert "No relevant regulatory guidelines found." in combined_str
        assert "No relevant cultural guidelines found." in combined_str
        assert sources == []

    def test_sorts_by_score_descending(self):
        """Results are sorted by similarity score descending."""
        reg_results = _mock_regulatory_results(3)
        cult_results = _mock_cultural_results(2)

        _, _, _, sources = _format_labeled_results(
            reg_results.points, cult_results.points
        )

        scores = [s["score"] for s in sources]
        assert scores == sorted(scores, reverse=True)

    def test_limits_to_top_k(self):
        """Limits combined results to top_k."""
        reg_results = _mock_regulatory_results(5)
        cult_results = _mock_cultural_results(5)

        _, _, _, sources = _format_labeled_results(
            reg_results.points, cult_results.points, top_k=3
        )

        assert len(sources) == 3

    def test_labels_sources_correctly(self):
        """Each result is labeled with correct source."""
        reg_results = _mock_regulatory_results(2)
        cult_results = _mock_cultural_results(2)

        _, _, _, sources = _format_labeled_results(
            reg_results.points, cult_results.points
        )

        reg_sources = [s for s in sources if s["source"] == "regulatory"]
        cult_sources = [s for s in sources if s["source"] == "cultural"]
        assert len(reg_sources) == 2
        assert len(cult_sources) == 2


class TestBuildCulturalFilter:
    """Tests for the _build_cultural_filter helper function."""

    def test_market_filter_always_present(self):
        """Market filter is always included."""
        f = _build_cultural_filter("malaysia", "all", "all_ages")
        # Should have market condition
        market_conditions = [
            c for c in f.must
            if hasattr(c, "key") and c.key == "market"
        ]
        assert len(market_conditions) == 1

    def test_ethnicity_filter_when_specific(self):
        """Ethnicity filter includes matching + 'all' when specific."""
        f = _build_cultural_filter("malaysia", "malay", "all_ages")
        ethnicity_conditions = [
            c for c in f.must
            if hasattr(c, "key") and c.key == "ethnicity"
        ]
        assert len(ethnicity_conditions) == 1
        # Should use MatchAny with ["malay", "all"]
        match = ethnicity_conditions[0].match
        assert hasattr(match, "any")
        assert "malay" in match.any
        assert "all" in match.any

    def test_no_ethnicity_filter_when_all(self):
        """No ethnicity filter when target is 'all'."""
        f = _build_cultural_filter("malaysia", "all", "all_ages")
        ethnicity_conditions = [
            c for c in f.must
            if hasattr(c, "key") and c.key == "ethnicity"
        ]
        assert len(ethnicity_conditions) == 0

    def test_age_group_filter_all_ages_only(self):
        """When target is 'all_ages', only include 'all_ages' guidelines."""
        f = _build_cultural_filter("malaysia", "all", "all_ages")
        age_conditions = [
            c for c in f.must
            if hasattr(c, "key") and c.key == "age_group"
        ]
        assert len(age_conditions) == 1
        match = age_conditions[0].match
        assert hasattr(match, "value")
        assert match.value == "all_ages"

    def test_age_group_filter_specific_includes_all_ages(self):
        """When target is specific, include both 'all_ages' and matching."""
        f = _build_cultural_filter("malaysia", "all", "children")
        age_conditions = [
            c for c in f.must
            if hasattr(c, "key") and c.key == "age_group"
        ]
        assert len(age_conditions) == 1
        match = age_conditions[0].match
        assert hasattr(match, "any")
        assert "all_ages" in match.any
        assert "children" in match.any
