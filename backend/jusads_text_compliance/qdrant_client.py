"""Simplified Qdrant client for JusAds Text Compliance

Thin wrapper around Qdrant collections to retrieve:
1. Regulatory rules (MCMC for Malaysia)
2. Cultural guidelines (ethnic-specific)
3. Persona narratives (target audience context)
"""

import logging
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from .config import (
    CULTURAL_COLLECTION,
    PERSONA_COLLECTION,
    QDRANT_API_KEY,
    QDRANT_URL,
    REGULATORY_COLLECTION_MALAYSIA,
    TOP_K_CULTURAL,
    TOP_K_REGULATORY,
)

logger = logging.getLogger(__name__)


class JusAdsQdrantClient:
    """Simplified Qdrant client for text compliance checking."""

    def __init__(self):
        """Initialize Qdrant client with credentials from config."""
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError(
                "QDRANT_URL and QDRANT_API_KEY must be set in environment"
            )

        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        logger.info("Initialized Qdrant client: %s", QDRANT_URL)

    def get_regulatory_rules(
        self, query_vector: list[float], market: str = "malaysia", top_k: int = None
    ) -> list[dict[str, Any]]:
        """Retrieve regulatory guidelines for the specified market.

        Args:
            query_vector: Embedding vector for the ad text.
            market: Target market ('malaysia' or 'singapore').
            top_k: Number of results to return (default: TOP_K_REGULATORY).

        Returns:
            List of regulatory guideline dicts with 'guideline_text' and metadata.
        """
        if top_k is None:
            top_k = TOP_K_REGULATORY

        collection_name = (
            REGULATORY_COLLECTION_MALAYSIA
            if market == "malaysia"
            else "singapore-imda-asas-guidelines"
        )

        try:
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
            ).points

            guidelines = []
            for result in results:
                payload = result.payload or {}
                guidelines.append({
                    "guideline_text": payload.get("guideline_text", ""),
                    "category": payload.get("category", ""),
                    "severity": payload.get("severity", ""),
                    "score": result.score,
                    "source": "regulatory",
                })

            logger.info(
                "Retrieved %d regulatory rules from %s", len(guidelines), collection_name
            )
            return guidelines

        except Exception as e:
            logger.error("Failed to retrieve regulatory rules: %s", str(e))
            return []

    def get_cultural_guidelines(
        self,
        query_vector: list[float],
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
        top_k: int = None,
    ) -> list[dict[str, Any]]:
        """Retrieve cultural guidelines filtered by market, ethnicity, and age group.

        Args:
            query_vector: Embedding vector for the ad text.
            market: Target market ('malaysia' or 'singapore').
            ethnicity: Target ethnicity ('malay', 'chinese', 'indian', 'all').
            age_group: Target age group ('all_ages', 'adults_only', 'children').
            top_k: Number of results to return (default: TOP_K_CULTURAL).

        Returns:
            List of cultural guideline dicts with 'guideline_text' and metadata.
        """
        if top_k is None:
            top_k = TOP_K_CULTURAL

        # Build filter conditions
        filter_conditions = [
            FieldCondition(key="market", match=MatchValue(value=market)),
            FieldCondition(key="age_group", match=MatchValue(value=age_group)),
        ]

        # If ethnicity is not 'all', filter by specific ethnicity OR 'all'
        if ethnicity != "all":
            # Note: Qdrant doesn't support OR at field level easily,
            # so we'll retrieve both and merge results
            # For simplicity, we'll just filter by specific ethnicity
            # and let the LLM handle broader context
            filter_conditions.append(
                FieldCondition(key="ethnicity", match=MatchValue(value=ethnicity))
            )

        query_filter = Filter(must=filter_conditions)

        try:
            results = self.client.query_points(
                collection_name=CULTURAL_COLLECTION,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
            ).points

            guidelines = []
            for result in results:
                payload = result.payload or {}
                guidelines.append({
                    "guideline_text": payload.get("guideline_text", ""),
                    "category": payload.get("category", ""),
                    "severity": payload.get("severity", ""),
                    "ethnicity": payload.get("ethnicity", ""),
                    "score": result.score,
                    "source": "cultural",
                })

            logger.info(
                "Retrieved %d cultural guidelines for %s/%s/%s",
                len(guidelines),
                market,
                ethnicity,
                age_group,
            )
            return guidelines

        except Exception as e:
            logger.error("Failed to retrieve cultural guidelines: %s", str(e))
            return []


