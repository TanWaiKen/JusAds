"""Embedding utilities using Cohere embed-v4 via AWS Bedrock

Produces 1536-dim vectors matching the existing Qdrant collections.
"""

import json
import logging
from typing import Optional

import boto3

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION_EMBED,
    AWS_SECRET_ACCESS_KEY,
    EMBED_MODEL_ID,
)

logger = logging.getLogger(__name__)


def _get_bedrock_client():
    """Create a Bedrock runtime client using .env credentials."""
    try:
        return boto3.client(
            service_name="bedrock-runtime",
            region_name=AWS_REGION_EMBED,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
    except Exception:
        # Fallback to default boto3 credential chain (IAM role, etc.)
        return boto3.client("bedrock-runtime", region_name=AWS_REGION_EMBED)


def embed_text(text: str, input_type: str = "search_query") -> Optional[list[float]]:
    """Generate embedding vector for a single text string.

    Args:
        text: Input text to embed.
        input_type: Cohere input type. Options:
            - "search_query": For query text (default)
            - "search_document": For document text

    Returns:
        1536-dimensional embedding vector, or None on failure.
    """
    if not text or not text.strip():
        logger.warning("Cannot embed empty text")
        return None

    try:
        client = _get_bedrock_client()
        body = json.dumps({
            "texts": [text],
            "input_type": input_type,
            "embedding_types": ["float"],
        })

        response = client.invoke_model(
            modelId=EMBED_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        embedding = result["embeddings"]["float"][0]
        logger.debug("Generated embedding for text (dim: %d)", len(embedding))
        return embedding

    except Exception as e:
        logger.error("Failed to generate embedding: %s", str(e))
        return None


def embed_batch(
    texts: list[str], input_type: str = "search_document"
) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of input texts to embed.
        input_type: Cohere input type.

    Returns:
        List of embedding vectors (1536-dim each).
    """
    if not texts:
        return []

    try:
        client = _get_bedrock_client()
        body = json.dumps({
            "texts": texts,
            "input_type": input_type,
            "embedding_types": ["float"],
        })

        response = client.invoke_model(
            modelId=EMBED_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        embeddings = result["embeddings"]["float"]
        logger.info("Generated %d embeddings", len(embeddings))
        return embeddings

    except Exception as e:
        logger.error("Failed to generate batch embeddings: %s", str(e))
        return [[0.0] * 1536 for _ in texts]  # Fallback to zero vectors
