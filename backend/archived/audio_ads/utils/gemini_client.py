"""
Gemini Client
==============
Shared Gemini API client + JSON response parser.
Uses the google.genai SDK with gemini-3-flash-preview.
"""

import json
import os
from google import genai
from google.genai import types


def get_client(api_key: str | None = None) -> genai.Client:
    """Create and return a Gemini client."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is required")
    return genai.Client(api_key=key)


def parse_json_response(text: str) -> list | dict:
    """
    Clean markdown fences and parse JSON from a Gemini response.

    Raises:
        RuntimeError on parse failure.
    """
    content = text.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini response as JSON: {e}\n{content}")
