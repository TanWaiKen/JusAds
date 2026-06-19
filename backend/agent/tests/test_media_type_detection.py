"""
test_media_type_detection.py
─────────────────────────────
Unit tests for the MIME-based media type detection utility.

Validates: Requirements 1.8
"""

import pytest
from agent.utils import detect_media_type, detect_media_type_from_filename


# ── detect_media_type tests ───────────────────────────────────────────────────


class TestDetectMediaType:
    """Tests for detect_media_type(mime_type) -> str."""

    # Image MIME types
    @pytest.mark.parametrize("mime", [
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "image/bmp",
        "image/tiff",
    ])
    def test_image_mime_types(self, mime):
        assert detect_media_type(mime) == "image"

    # Audio MIME types
    @pytest.mark.parametrize("mime", [
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        "audio/flac",
        "audio/aac",
        "audio/webm",
        "audio/x-wav",
    ])
    def test_audio_mime_types(self, mime):
        assert detect_media_type(mime) == "audio"

    # Video MIME types
    @pytest.mark.parametrize("mime", [
        "video/mp4",
        "video/webm",
        "video/ogg",
        "video/quicktime",
        "video/x-msvideo",
        "video/mpeg",
    ])
    def test_video_mime_types(self, mime):
        assert detect_media_type(mime) == "video"

    # Text/other MIME types → "text"
    @pytest.mark.parametrize("mime", [
        "text/plain",
        "text/html",
        "application/octet-stream",
        "application/pdf",
        "application/json",
        "application/xml",
        "multipart/form-data",
    ])
    def test_other_mime_types_return_text(self, mime):
        assert detect_media_type(mime) == "text"

    def test_empty_string_returns_text(self):
        assert detect_media_type("") == "text"

    def test_none_returns_text(self):
        # None is falsy, should return "text"
        assert detect_media_type(None) == "text"

    def test_case_insensitive(self):
        assert detect_media_type("IMAGE/PNG") == "image"
        assert detect_media_type("Audio/MPEG") == "audio"
        assert detect_media_type("Video/MP4") == "video"


# ── detect_media_type_from_filename tests ─────────────────────────────────────


class TestDetectMediaTypeFromFilename:
    """Tests for detect_media_type_from_filename(filename) -> str."""

    @pytest.mark.parametrize("filename,expected", [
        ("photo.jpg", "image"),
        ("photo.jpeg", "image"),
        ("photo.png", "image"),
        ("photo.gif", "image"),
        ("photo.bmp", "image"),
        ("photo.svg", "image"),
    ])
    def test_image_filenames(self, filename, expected):
        assert detect_media_type_from_filename(filename) == expected

    @pytest.mark.parametrize("filename,expected", [
        ("song.mp3", "audio"),
        ("song.wav", "audio"),
        ("song.flac", "audio"),
        ("song.aac", "audio"),
    ])
    def test_audio_filenames(self, filename, expected):
        assert detect_media_type_from_filename(filename) == expected

    @pytest.mark.parametrize("filename,expected", [
        ("clip.mp4", "video"),
        ("clip.webm", "video"),
        ("clip.avi", "video"),
        ("clip.mov", "video"),
        ("clip.mpeg", "video"),
    ])
    def test_video_filenames(self, filename, expected):
        assert detect_media_type_from_filename(filename) == expected

    @pytest.mark.parametrize("filename,expected", [
        ("doc.txt", "text"),
        ("page.html", "text"),
        ("data.json", "text"),
        ("file.pdf", "text"),
        ("unknown.xyz", "text"),
        ("noextension", "text"),
    ])
    def test_text_and_other_filenames(self, filename, expected):
        assert detect_media_type_from_filename(filename) == expected

    def test_empty_filename_returns_text(self):
        assert detect_media_type_from_filename("") == "text"

    def test_none_filename_returns_text(self):
        assert detect_media_type_from_filename(None) == "text"
