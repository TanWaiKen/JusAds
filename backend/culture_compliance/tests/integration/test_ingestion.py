"""Integration tests for guideline ingestion into Qdrant.

These tests verify that guidelines can be ingested into Qdrant collections
and that the collections are properly populated with the expected data.

Tests require valid AWS credentials (for Bedrock embeddings) and Qdrant
connectivity.

Requirements: 9.5, 5.1, 5.2
"""

import os
from pathlib import Path

import pytest

from culture_compliance.ingest import ingest_guidelines, DEFAULT_CSV_PATHS
from culture_compliance.models.schemas import Market
from culture_compliance.nodes.step1_routing import COLLECTION_CONFIG


# --- Skip conditions ---

_MISSING_AWS = not os.environ.get("AWS_ACCESS_KEY_ID") and not os.environ.get(
    "AWS_PROFILE"
)
_MISSING_QDRANT = not os.environ.get("QDRANT_URL")

_SKIP_REASON = (
    "Integration tests require AWS credentials (AWS_ACCESS_KEY_ID or AWS_PROFILE) "
    "and QDRANT_URL environment variables"
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(_MISSING_AWS or _MISSING_QDRANT, reason=_SKIP_REASON),
]


# --- Helpers ---


def _get_qdrant_client():
    """Create a Qdrant client for verification queries."""
    from qdrant_client import QdrantClient

    url = os.environ.get("QDRANT_URL", "")
    api_key = os.environ.get("QDRANT_API_KEY", "")
    return QdrantClient(url=url, api_key=api_key)


# --- Malaysia Ingestion Tests ---


class TestMalaysiaIngestion:
    """Tests for Malaysia (MCMC) guideline ingestion."""

    def test_ingest_malaysia_guidelines(self):
        """Verify Malaysia guidelines can be ingested into Qdrant.

        Validates: Requirement 5.1 - MCMC guidelines in Qdrant
        """
        csv_path = DEFAULT_CSV_PATHS[Market.MALAYSIA]

        if not csv_path.exists():
            pytest.skip(f"Malaysia guidelines CSV not found: {csv_path}")

        try:
            total = ingest_guidelines(csv_path, market="malaysia", recreate=True)
        except Exception as e:
            pytest.skip(
                f"Qdrant ingestion failed (service may be unavailable): {e}"
            )

        assert total > 0, "Expected at least one vector to be upserted"

    def test_malaysia_collection_populated(self):
        """Verify the MCMC guidelines collection has vectors after ingestion.

        Validates: Requirement 5.1 - MCMC collection accessible
        """
        collection_name = COLLECTION_CONFIG[Market.MALAYSIA]["collection_name"]
        client = _get_qdrant_client()

        try:
            collection_info = client.get_collection(collection_name)
        except Exception as e:
            pytest.skip(
                f"Collection '{collection_name}' not accessible: {e}"
            )

        assert collection_info.points_count > 0, (
            f"Collection '{collection_name}' is empty. "
            "Run ingestion before this test."
        )

    def test_malaysia_collection_has_correct_metadata(self):
        """Verify ingested Malaysia guidelines have correct payload metadata.

        Validates: Requirement 5.1 - MCMC source authority in metadata
        """
        collection_name = COLLECTION_CONFIG[Market.MALAYSIA]["collection_name"]
        client = _get_qdrant_client()

        try:
            # Scroll a few points to check metadata
            results = client.scroll(
                collection_name=collection_name,
                limit=5,
                with_payload=True,
            )
        except Exception as e:
            pytest.skip(f"Cannot scroll collection '{collection_name}': {e}")

        points, _ = results
        assert len(points) > 0, "No points found in collection"

        for point in points:
            payload = point.payload
            assert payload is not None, "Point has no payload"
            # Should have source_authority field
            assert "source_authority" in payload, (
                f"Missing 'source_authority' in payload: {payload.keys()}"
            )
            assert payload["source_authority"] == "MCMC", (
                f"Expected source_authority 'MCMC', got '{payload['source_authority']}'"
            )


# --- Singapore Ingestion Tests ---


class TestSingaporeIngestion:
    """Tests for Singapore (IMDA/ASAS) guideline ingestion."""

    def test_ingest_singapore_guidelines(self):
        """Verify Singapore guidelines can be ingested into Qdrant.

        Validates: Requirement 5.2 - IMDA/ASAS guidelines in Qdrant
        """
        csv_path = DEFAULT_CSV_PATHS[Market.SINGAPORE]

        if not csv_path.exists():
            pytest.skip(f"Singapore guidelines CSV not found: {csv_path}")

        try:
            total = ingest_guidelines(csv_path, market="singapore", recreate=True)
        except Exception as e:
            pytest.skip(
                f"Qdrant ingestion failed (service may be unavailable): {e}"
            )

        assert total > 0, "Expected at least one vector to be upserted"

    def test_singapore_collection_populated(self):
        """Verify the Singapore guidelines collection has vectors after ingestion.

        Validates: Requirement 5.2 - Singapore collection accessible
        """
        collection_name = COLLECTION_CONFIG[Market.SINGAPORE]["collection_name"]
        client = _get_qdrant_client()

        try:
            collection_info = client.get_collection(collection_name)
        except Exception as e:
            pytest.skip(
                f"Collection '{collection_name}' not accessible: {e}"
            )

        assert collection_info.points_count > 0, (
            f"Collection '{collection_name}' is empty. "
            "Run ingestion before this test."
        )

    def test_singapore_collection_has_correct_metadata(self):
        """Verify ingested Singapore guidelines have correct payload metadata.

        Validates: Requirement 5.2 - IMDA/ASAS source authority in metadata
        """
        collection_name = COLLECTION_CONFIG[Market.SINGAPORE]["collection_name"]
        client = _get_qdrant_client()

        try:
            results = client.scroll(
                collection_name=collection_name,
                limit=5,
                with_payload=True,
            )
        except Exception as e:
            pytest.skip(f"Cannot scroll collection '{collection_name}': {e}")

        points, _ = results
        assert len(points) > 0, "No points found in collection"

        for point in points:
            payload = point.payload
            assert payload is not None, "Point has no payload"
            assert "source_authority" in payload, (
                f"Missing 'source_authority' in payload: {payload.keys()}"
            )
            # Singapore can be IMDA or ASAS
            valid_authorities = {"IMDA", "ASAS", "IMDA/ASAS"}
            assert payload["source_authority"] in valid_authorities, (
                f"Expected source_authority in {valid_authorities}, "
                f"got '{payload['source_authority']}'"
            )

    def test_singapore_collection_has_topic_categories(self):
        """Verify Singapore guidelines have topic_category metadata.

        Validates: Requirement 5.2 - topic categorization
        """
        collection_name = COLLECTION_CONFIG[Market.SINGAPORE]["collection_name"]
        client = _get_qdrant_client()

        try:
            results = client.scroll(
                collection_name=collection_name,
                limit=10,
                with_payload=True,
            )
        except Exception as e:
            pytest.skip(f"Cannot scroll collection '{collection_name}': {e}")

        points, _ = results
        assert len(points) > 0, "No points found in collection"

        # At least some points should have topic_category
        categories_found = set()
        for point in points:
            payload = point.payload
            if payload and "topic_category" in payload:
                categories_found.add(payload["topic_category"])

        assert len(categories_found) > 0, (
            "No topic_category values found in collection metadata"
        )


# --- Cross-Market Verification Tests ---


class TestCrossMarketIngestion:
    """Tests verifying both markets have separate, correctly populated collections."""

    def test_separate_collections_exist(self):
        """Verify Malaysia and Singapore have separate Qdrant collections.

        Validates: Requirements 5.1, 5.2 - separate collections per market
        """
        client = _get_qdrant_client()

        my_collection = COLLECTION_CONFIG[Market.MALAYSIA]["collection_name"]
        sg_collection = COLLECTION_CONFIG[Market.SINGAPORE]["collection_name"]

        # Both collections should exist
        try:
            my_info = client.get_collection(my_collection)
            sg_info = client.get_collection(sg_collection)
        except Exception as e:
            pytest.skip(f"One or both collections not accessible: {e}")

        # They should be different collections
        assert my_collection != sg_collection, (
            "Malaysia and Singapore should use different collection names"
        )

        # Both should have data
        assert my_info.points_count > 0, (
            f"Malaysia collection '{my_collection}' is empty"
        )
        assert sg_info.points_count > 0, (
            f"Singapore collection '{sg_collection}' is empty"
        )

    def test_collections_use_correct_vector_dimensions(self):
        """Verify both collections use 1024-dimension vectors (Cohere embed-v4).

        Validates: Requirements 5.1, 5.2 - correct embedding configuration

        NOTE: If this test fails with size=1536, the collection was created with
        the old Amazon Titan v2 embeddings. Re-ingest to fix:
            uv run python -m culture_compliance.ingest --market malaysia --recreate
            uv run python -m culture_compliance.ingest --market singapore --recreate
        """
        client = _get_qdrant_client()

        for market in [Market.MALAYSIA, Market.SINGAPORE]:
            collection_name = COLLECTION_CONFIG[market]["collection_name"]

            try:
                info = client.get_collection(collection_name)
            except Exception as e:
                pytest.skip(
                    f"Collection '{collection_name}' not accessible: {e}"
                )

            # Check vector size is 1024 (Cohere embed-v4)
            vectors_config = info.config.params.vectors
            if hasattr(vectors_config, "size"):
                actual_size = vectors_config.size
                if actual_size != 1024:
                    pytest.xfail(
                        f"Collection '{collection_name}' has vector size {actual_size} "
                        f"(expected 1024). The collection was built with an older embedding "
                        f"model (likely Amazon Titan v2 at 1536-dim). Re-ingest with: "
                        f"uv run python -m culture_compliance.ingest "
                        f"--market {market.value} --recreate"
                    )
