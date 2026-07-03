"""
embeddings.py
─────────────
Text embeddings via Google Gemini (text-embedding-004). Uses the same Vertex AI
client already configured for the project. Works in all regions.
"""

import logging
from typing import Optional

from shared.clients import gemini

logger = logging.getLogger(__name__)

# Gemini text-embedding-004 produces 768-dim vectors by default.
EMBED_DIMENSIONS = 768
_MODEL_ID = "text-embedding-004"


def embed_text(text: str, input_type: str = "search_document") -> list[float]:
    """Embed a single text string using Gemini text-embedding-004.

    Args:
        text: The text to embed (max ~2048 tokens).
        input_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for search.

    Returns:
        A list of floats (768-dim embedding vector).
    """
    # Map simple input_type to Gemini's task_type enum.
    task_type = "RETRIEVAL_QUERY" if "query" in input_type else "RETRIEVAL_DOCUMENT"

    try:
        result = gemini.models.embed_content(
            model=_MODEL_ID,
            contents=text[:8000],
            config={"task_type": task_type},
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error("[Embeddings] Gemini embed failed: %s", e)
        raise


def embed_batch(texts: list[str], input_type: str = "search_document") -> list[list[float]]:
    """Embed a batch of texts. Gemini supports batch natively (up to 100).

    Args:
        texts: List of texts to embed.
        input_type: "search_document" or "search_query".

    Returns:
        List of embedding vectors (same order as input).
    """
    task_type = "RETRIEVAL_QUERY" if "query" in input_type else "RETRIEVAL_DOCUMENT"

    try:
        result = gemini.models.embed_content(
            model=_MODEL_ID,
            contents=texts[:100],  # Gemini batch limit
            config={"task_type": task_type},
        )
        return [e.values for e in result.embeddings]
    except Exception as e:
        logger.error("[Embeddings] Gemini batch embed failed: %s", e)
        # Fallback to sequential on batch failure.
        return [embed_text(t, input_type) for t in texts]
