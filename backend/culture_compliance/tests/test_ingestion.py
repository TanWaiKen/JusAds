"""Unit tests for guideline ingestion.

Tests validate that the ingest_guidelines function correctly:
- Creates the correct collection for the specified market
- Returns an error when the CSV file is missing
- Returns an error when the CSV file is empty
- Stores metadata (source_authority, topic_category, guideline_text) correctly

Requirements: 6.3, 6.5, 6.6
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from culture_compliance.ingest import ingest_guidelines


@pytest.fixture
def mock_qdrant_client():
    """Create a mock Qdrant client."""
    with patch("culture_compliance.qdrant_store._client", new_callable=MagicMock) as mock_client:
        yield mock_client


@pytest.fixture
def mock_embed_batch():
    """Mock the embed_batch function to return fake embeddings."""
    with patch("culture_compliance.embeddings.embed_batch") as mock_embed:
        # Return 1024-dim vectors for each text in the batch
        mock_embed.side_effect = lambda texts, **kwargs: [[0.1] * 1024 for _ in texts]
        yield mock_embed


@pytest.fixture
def mock_ensure_collection():
    """Mock ensure_collection to avoid real Qdrant calls."""
    with patch("culture_compliance.qdrant_store.ensure_collection") as mock_ec:
        yield mock_ec


@pytest.fixture
def singapore_csv(tmp_path):
    """Create a temporary Singapore-format CSV file with standard columns."""
    csv_file = tmp_path / "singapore_guidelines.csv"
    csv_file.write_text(
        "source_authority,topic_category,guideline_text\n"
        "IMDA,Racial/Religious Harmony,Advertisements must not offend racial or religious groups\n"
        "ASAS,Decency,Advertisements must not contain indecent content\n",
        encoding="utf-8",
    )
    return csv_file


@pytest.fixture
def malaysia_csv(tmp_path):
    """Create a temporary Malaysia-format CSV file with MCMC columns."""
    csv_file = tmp_path / "mcmc_guidelines.csv"
    csv_file.write_text(
        "category,rule,description\n"
        "Religious Sensitivity,No blasphemy,Content must not insult any religion\n"
        "Ethnic/Racial,No stereotyping,Content must not stereotype ethnic groups\n",
        encoding="utf-8",
    )
    return csv_file


class TestSuccessfulIngestion:
    """Tests for successful guideline ingestion creating the correct collection."""

    def test_ingestion_creates_singapore_collection(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Ingesting Singapore guidelines creates the singapore-imda-asas-guidelines collection."""
        result = ingest_guidelines(singapore_csv, market="singapore")

        mock_ensure_collection.assert_called_once_with(
            name="singapore-imda-asas-guidelines", recreate=False
        )
        assert result == 2

    def test_ingestion_creates_malaysia_collection(
        self, malaysia_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Ingesting Malaysia guidelines creates the mcmc-guidelines collection."""
        result = ingest_guidelines(malaysia_csv, market="malaysia")

        mock_ensure_collection.assert_called_once_with(
            name="mcmc-guidelines", recreate=False
        )
        assert result == 2

    def test_ingestion_returns_correct_count(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Ingestion returns the number of vectors upserted."""
        result = ingest_guidelines(singapore_csv, market="singapore")

        assert result == 2

    def test_ingestion_upserts_to_correct_collection(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Ingestion upserts points to the correct Qdrant collection."""
        ingest_guidelines(singapore_csv, market="singapore")

        mock_qdrant_client.upsert.assert_called_once()
        call_kwargs = mock_qdrant_client.upsert.call_args
        assert call_kwargs.kwargs["collection_name"] == "singapore-imda-asas-guidelines"

    def test_ingestion_with_recreate_flag(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Ingestion passes recreate flag to ensure_collection."""
        ingest_guidelines(singapore_csv, market="singapore", recreate=True)

        mock_ensure_collection.assert_called_once_with(
            name="singapore-imda-asas-guidelines", recreate=True
        )

    def test_ingestion_case_insensitive_market(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Ingestion handles case-insensitive market values."""
        result = ingest_guidelines(singapore_csv, market="Singapore")

        mock_ensure_collection.assert_called_once_with(
            name="singapore-imda-asas-guidelines", recreate=False
        )
        assert result == 2


class TestMissingCSVFile:
    """Tests for missing CSV file error handling."""

    def test_missing_csv_raises_file_not_found(self):
        """Raises FileNotFoundError when CSV file does not exist."""
        non_existent = Path("/tmp/does_not_exist_guidelines.csv")

        with pytest.raises(FileNotFoundError) as exc_info:
            ingest_guidelines(non_existent, market="singapore")

        assert "not found" in str(exc_info.value).lower()

    def test_missing_csv_error_includes_path(self):
        """FileNotFoundError message includes the file path."""
        non_existent = Path("/tmp/missing_file.csv")

        with pytest.raises(FileNotFoundError) as exc_info:
            ingest_guidelines(non_existent, market="malaysia")

        assert "missing_file.csv" in str(exc_info.value)


class TestEmptyCSVFile:
    """Tests for empty CSV file error handling."""

    def test_empty_csv_raises_value_error(self, tmp_path):
        """Raises ValueError when CSV file is completely empty."""
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("", encoding="utf-8")

        with pytest.raises((ValueError, StopIteration)):
            ingest_guidelines(empty_csv, market="singapore")

    def test_headers_only_csv_raises_value_error(
        self, tmp_path, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Raises ValueError when CSV has headers but no data rows."""
        headers_only = tmp_path / "headers_only.csv"
        headers_only.write_text(
            "source_authority,topic_category,guideline_text\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ingest_guidelines(headers_only, market="singapore")

        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_rows_raises_value_error(
        self, tmp_path, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Raises ValueError when CSV rows contain only whitespace."""
        whitespace_csv = tmp_path / "whitespace.csv"
        whitespace_csv.write_text(
            "source_authority,topic_category,guideline_text\n"
            " , , \n"
            " , , \n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ingest_guidelines(whitespace_csv, market="singapore")

        assert "empty" in str(exc_info.value).lower()


class TestMetadataStorage:
    """Tests for correct metadata storage in Qdrant payloads."""

    def test_singapore_metadata_stored_correctly(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Singapore guidelines store source_authority, topic_category, guideline_text in payload."""
        ingest_guidelines(singapore_csv, market="singapore")

        # Get the points that were upserted
        upsert_call = mock_qdrant_client.upsert.call_args
        points = upsert_call.kwargs["points"]

        # Check first point metadata
        payload_0 = points[0].payload
        assert payload_0["source_authority"] == "IMDA"
        assert payload_0["topic_category"] == "Racial/Religious Harmony"
        assert payload_0["guideline_text"] == "Advertisements must not offend racial or religious groups"
        assert payload_0["source"] == "singapore_guidelines.csv"

        # Check second point metadata
        payload_1 = points[1].payload
        assert payload_1["source_authority"] == "ASAS"
        assert payload_1["topic_category"] == "Decency"
        assert payload_1["guideline_text"] == "Advertisements must not contain indecent content"

    def test_malaysia_metadata_normalized_correctly(
        self, malaysia_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Malaysia MCMC guidelines normalize category/rule/description to standard metadata."""
        ingest_guidelines(malaysia_csv, market="malaysia")

        upsert_call = mock_qdrant_client.upsert.call_args
        points = upsert_call.kwargs["points"]

        payload_0 = points[0].payload
        assert payload_0["source_authority"] == "MCMC"
        assert payload_0["topic_category"] == "Religious Sensitivity"
        assert "No blasphemy" in payload_0["guideline_text"]
        assert "Content must not insult any religion" in payload_0["guideline_text"]

    def test_row_text_field_stored_in_payload(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Each point payload includes the row_text field for retrieval display."""
        ingest_guidelines(singapore_csv, market="singapore")

        upsert_call = mock_qdrant_client.upsert.call_args
        points = upsert_call.kwargs["points"]

        for point in points:
            assert "row_text" in point.payload
            assert point.payload["row_text"]  # non-empty

    def test_points_have_uuid_ids(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Each upserted point has a valid UUID string as its ID."""
        import uuid

        ingest_guidelines(singapore_csv, market="singapore")

        upsert_call = mock_qdrant_client.upsert.call_args
        points = upsert_call.kwargs["points"]

        for point in points:
            # Should not raise ValueError if it's a valid UUID
            uuid.UUID(point.id)

    def test_points_have_correct_dimension_vectors(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """Each upserted point has a 1024-dimensional embedding vector."""
        ingest_guidelines(singapore_csv, market="singapore")

        upsert_call = mock_qdrant_client.upsert.call_args
        points = upsert_call.kwargs["points"]

        for point in points:
            assert len(point.vector) == 1024

    def test_embed_batch_called_with_row_texts(
        self, singapore_csv, mock_qdrant_client, mock_embed_batch, mock_ensure_collection
    ):
        """embed_batch is called with the text representations of CSV rows."""
        ingest_guidelines(singapore_csv, market="singapore")

        mock_embed_batch.assert_called_once()
        texts = mock_embed_batch.call_args[0][0]
        assert len(texts) == 2
        # Each text should be a pipe-separated representation of the row
        for text in texts:
            assert "|" in text


class TestUnsupportedMarket:
    """Tests for unsupported market values."""

    def test_unsupported_market_raises_value_error(self, singapore_csv):
        """Raises ValueError for unsupported market values."""
        with pytest.raises(ValueError) as exc_info:
            ingest_guidelines(singapore_csv, market="japan")

        assert "unsupported" in str(exc_info.value).lower()
        assert "japan" in str(exc_info.value).lower()
