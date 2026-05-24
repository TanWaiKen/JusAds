"""
embeddings.py
─────────────
Embed text using Amazon Titan Text Embeddings v2 via AWS Bedrock.
"""

import json
import time
import random

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from .config import AWS_REGION_EMBED, EMBED_DIMENSIONS, EMBED_MODEL_ID

# 1. Configure client with ADAPTIVE retries
_config = Config(
    retries={
        "max_attempts": 10,
        "mode": "adaptive"
    }
)
_bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION_EMBED, config=_config)


def embed_text(text: str, max_retries: int = 5, input_type: str = "search_document") -> list[float]:
    """Embed a single text string using Cohere format."""
    body = json.dumps({
        "texts": [text],
        "input_type": input_type,
        "truncate": "NONE",
        "embedding_types": ["float"]
    })
    
    for attempt in range(max_retries):
        try:
            response = _bedrock_runtime.invoke_model(
                modelId=EMBED_MODEL_ID,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read())
            # Cohere embed-v4 returns embeddings under "embeddings.float" 
            # when embedding_types is specified
            if "embeddings" in response_body:
                embeddings = response_body["embeddings"]
                if isinstance(embeddings, dict) and "float" in embeddings:
                    return embeddings["float"][0]
                elif isinstance(embeddings, list):
                    return embeddings[0]
            raise Exception(f"Unexpected response structure: {list(response_body.keys())}")
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ThrottlingException":
                if attempt == max_retries - 1:
                    raise e
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"  ⚠️  Throttled. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            raise e
    
    raise Exception("Max retries exceeded.")


def embed_batch(texts: list[str], input_type: str = "search_document") -> list[list[float]]:
    """Embed a batch of texts natively (Cohere supports this)."""
    if not texts:
        return []
        
    body = json.dumps({
        "texts": texts,
        "input_type": input_type,
        "truncate": "NONE",
        "embedding_types": ["float"]
    })
    
    response = _bedrock_runtime.invoke_model(
        modelId=EMBED_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    response_body = json.loads(response["body"].read())
    # Cohere embed-v4 returns embeddings under "embeddings.float"
    # when embedding_types is specified
    if "embeddings" in response_body:
        embeddings = response_body["embeddings"]
        if isinstance(embeddings, dict) and "float" in embeddings:
            return embeddings["float"]
        elif isinstance(embeddings, list):
            return embeddings
    raise Exception(f"Unexpected response structure: {list(response_body.keys())}")

