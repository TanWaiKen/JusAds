"""
utils.py
────────
Shared utility functions for the compliance pipeline.
"""

import mimetypes


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
