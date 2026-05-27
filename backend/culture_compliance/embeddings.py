"""
embeddings.py
─────────────
Embed text using Gemini's text-embedding-004 model.
"""

import logging
from .gemini_client import get_client

logger = logging.getLogger(__name__)


def embed_text(text: str, max_retries: int = 5, input_type: str = "search_document") -> list[float]:
    """Embed a single text string using Gemini text-embedding-004."""
    if not text:
        return []
        
    client = get_client()
    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.error("Gemini text embedding failed: %s", str(e))
        raise e


def embed_batch(texts: list[str], input_type: str = "search_document") -> list[list[float]]:
    """Embed a batch of texts natively using Gemini text-embedding-004."""
    if not texts:
        return []
        
    client = get_client()
    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=texts,
        )
        return [embedding.values for embedding in response.embeddings]
    except Exception as e:
        logger.error("Gemini batch text embedding failed: %s", str(e))
        raise e


