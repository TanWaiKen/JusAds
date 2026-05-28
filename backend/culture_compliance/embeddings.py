"""
embeddings.py
─────────────
Embed text using Cohere embed-v4 via AWS Bedrock (1536-dim).
Replaces the deprecated/broken Gemini text-embedding-004.
"""

import json
import logging
from typing import Optional

import boto3
import os

logger = logging.getLogger(__name__)

AWS_REGION_EMBED = os.environ.get("AWS_REGION_EMBED", "ap-southeast-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
EMBED_MODEL_ID = "global.cohere.embed-v4:0"

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
        # Fallback to default boto3 credential chain
        return boto3.client("bedrock-runtime", region_name=AWS_REGION_EMBED)


def embed_text(text: str, max_retries: int = 5, input_type: str = "search_document") -> list[float]:
    """Embed a single text string using Cohere embed-v4."""
    if not text or not text.strip():
        return []

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
        return result["embeddings"]["float"][0]
    except Exception as e:
        logger.error("Cohere text embedding failed: %s", str(e))
        raise e


def embed_batch(texts: list[str], input_type: str = "search_document") -> list[list[float]]:
    """Embed a batch of texts natively using Cohere embed-v4."""
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
        return result["embeddings"]["float"]
    except Exception as e:
        logger.error("Cohere batch text embedding failed: %s", str(e))
        raise e
