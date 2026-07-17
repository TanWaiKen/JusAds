"""
utils.py
────────
Shared utility functions for the compliance pipeline.
"""

import mimetypes

# Ensure common web formats are recognized (mimetypes depends on OS registry which may lack them)
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('audio/webm', '.weba')
def detect_media_type(mime_type: str) -> str:
    """Classify a MIME type string into a media category.

    Returns one of: "image", "audio", "video", or "text".

    Rules:
      - MIME starting with "image/" → "image"
      - MIME starting with "audio/" → "audio"
      - MIME starting with "video/" → "video"
      - All others (including application/octet-stream, None, empty) → "text"
    """
    if not mime_type:
        return "text"

    mime_lower = mime_type.lower()

    if mime_lower.startswith("image/"):
        return "image"
    elif mime_lower.startswith("audio/"):
        return "audio"
    elif mime_lower.startswith("video/"):
        return "video"
    else:
        return "text"


def detect_media_type_from_filename(filename: str) -> str:
    """Detect media type from a filename using Python's mimetypes module.

    Uses mimetypes.guess_type to determine the MIME type from the filename,
    then delegates to detect_media_type for classification.

    Args:
        filename: The filename (e.g., "photo.jpg", "song.mp3")

    Returns:
        One of: "image", "audio", "video", or "text"
    """
    if not filename:
        return "text"

    mime, _ = mimetypes.guess_type(filename)
    return detect_media_type(mime or "")


def parse_json_res(text: str) -> dict:
    """Safely parse JSON from a model response text, stripping markdown code blocks if present."""
    import json
    if not text:
        return {}
    
    text = text.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```"):
        # Find first newline
        first_newline = text.find("\n")
        if first_newline != -1:
            # Check if it ends with ```
            if text.endswith("```"):
                text = text[first_newline + 1:-3].strip()
            else:
                text = text[first_newline + 1:].strip()
                
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract the JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            json_str = text[start:end+1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # Try cleaning up common JSON trailing commas
                import re
                # Remove trailing commas before closing braces/brackets
                json_str_clean = re.sub(r',\s*([\]}])', r'\1', json_str)
                try:
                    return json.loads(json_str_clean)
                except json.JSONDecodeError:
                    raise e
        raise
