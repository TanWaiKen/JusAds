"""Embedding utilities using Google Gemini text-embedding-004

Provides text embedding for semantic search in Qdrant collections.
"""

import logging
from typing import Optional

from google import genai
from google.genai import types

from .config import EMBED_MODEL_ID, GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# Initialize Gemini client
client = genai.Client(api_key=GOOGLE_API_KEY)


def embed_text(text: str, task_type: str = "RETRIEVAL_QUERY") -> Optional[list[float]]:
    """Generate embedding vector for a single text string.

    Args:
        text: Input text to embed.
        task_type: Task type for embedding model. Options:
            - "RETRIEVAL_QUERY": For query text (default)
            - "RETRIEVAL_DOCUMENT": For document text

    Returns:
        768-dimensional embedding vector, or None on failure.
    """
    if not text or not text.strip():
        logger.warning("Cannot embed empty text")
        return None

    try:
        response = client.models.embed_content(
            model=EMBED_MODEL_ID,
            contents=text,
        )
        embedding = response.embeddings[0].values
        logger.debug("Generated embedding for text (length: %d)", len(text))
        return embedding

    except Exception as e:
        logger.error("Failed to generate embedding: %s", str(e))
        return None


def embed_batch(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of input texts to embed.
        task_type: Task type for embedding model.

    Returns:
        List of embedding vectors (may contain None for failed embeddings).
    """
    embeddings = []
    for text in texts:
        emb = embed_text(text, task_type=task_type)
        embeddings.append(emb if emb else [0.0] * 768)  # Fallback to zero vector

    logger.info("Generated %d embeddings", len(embeddings))
    return embeddings
