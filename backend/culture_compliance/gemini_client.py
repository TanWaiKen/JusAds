"""
Gemini Client
==============
Shared Gemini API client + JSON response parser + multimodal handlers.
Uses the google.genai SDK.
"""

import json
import logging
import os
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


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


def generate_text(
    prompt: str,
    system_instruction: str | None = None,
    model: str = "gemini-2.5-flash",
    json_mode: bool = False,
) -> str:
    """Generate text from a prompt using Gemini."""
    client = get_client()
    config = types.GenerateContentConfig(
        temperature=0.0,
        system_instruction=system_instruction,
    )
    if json_mode:
        config.response_mime_type = "application/json"

    logger.info("Invoking Gemini text generation model '%s'", model)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return response.text


def analyze_image(
    image_bytes: bytes,
    prompt: str,
    mime_type: str = "image/jpeg",
    model: str = "gemini-2.5-flash",
) -> str:
    """Analyze image bytes with a prompt using Gemini."""
    client = get_client()
    
    logger.info("Analyzing image using Gemini model '%s' (mime_type=%s)", model, mime_type)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
        ),
    )
    return response.text


def analyze_video(
    video_path: str,
    prompt: str,
    model: str = "gemini-2.5-flash",
    json_mode: bool = False,
) -> str:
    """Uploads a video to Gemini File API, waits for it to become ACTIVE, runs analysis, and deletes the file."""
    client = get_client()
    
    logger.info("Uploading video '%s' to Gemini File API...", video_path)
    uploaded_file = client.files.upload(file=video_path)
    file_name = uploaded_file.name
    
    try:
        # Poll for processing completion
        logger.info("Waiting for Gemini File API processing on '%s'...", file_name)
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=file_name)
            
        if uploaded_file.state.name != "ACTIVE":
            raise RuntimeError(
                f"Gemini File API processing failed for '{video_path}' with state '{uploaded_file.state.name}'"
            )
            
        logger.info("Gemini File active. Running multimodal analysis...")
        config = types.GenerateContentConfig(temperature=0.0)
        if json_mode:
            config.response_mime_type = "application/json"
            
        response = client.models.generate_content(
            model=model,
            contents=[uploaded_file, prompt],
            config=config,
        )
        return response.text
        
    finally:
        # Always ensure deletion of the cloud file to prevent leak
        logger.info("Cleaning up Gemini File API object '%s'...", file_name)
        try:
            client.files.delete(name=file_name)
            logger.info("Successfully deleted Gemini File API object '%s'", file_name)
        except Exception as e:
            logger.warning("Failed to delete Gemini File API object '%s': %s", file_name, str(e))
