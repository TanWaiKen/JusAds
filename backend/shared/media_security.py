"""Shared media-upload validation and lightweight abuse controls.

The helpers here are intentionally independent from FastAPI route state. Routes
can stream an ``UploadFile`` through :func:`stream_validated_upload`, persist
only the returned private path/key metadata, then remove the temporary file in
a ``finally`` block with :func:`remove_temp_file`.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import tempfile
import time
import unicodedata
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Awaitable, Iterable, TypeVar

DEFAULT_CHUNK_SIZE = 64 * 1024
MAX_SIGNATURE_BYTES = 4096
_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(filename: str, default: str = "asset.bin", max_length: int = 120) -> str:
    """Return a single safe, ASCII filename without directory components."""
    value = unicodedata.normalize("NFKC", str(filename or ""))
    value = value.replace("\\", "/").rsplit("/", 1)[-1]
    value = "".join(ch for ch in value if ch.isprintable())
    value = _UNSAFE_FILENAME_RE.sub("_", value).strip(" ._-")
    if not value or value in {".", ".."}:
        value = default

    suffix = Path(value).suffix[:16]
    stem_limit = max(1, max_length - len(suffix))
    stem = Path(value).stem[:stem_limit].rstrip(" ._-") or "asset"
    return f"{stem}{suffix}"[:max_length]


class MediaSecurityError(ValueError):
    """A stable, client-safe media validation failure."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    path: str
    original_filename: str
    filename: str
    size: int
    sha256: str
    media_type: str
    mime_type: str


_EXTENSIONS_BY_MEDIA = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp"},
    "audio": {".mp3", ".wav", ".ogg", ".m4a"},
    "video": {".mp4", ".mov", ".webm"},
    "text": {".txt"},
}


def detect_signature(header: bytes, *, filename: str = "", declared_type: str = "") -> tuple[str, str]:
    """Detect a conservative media class and MIME type from magic bytes."""
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image", "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image", "image/webp"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio", "audio/wav"
    if header.startswith(b"OggS"):
        return "audio", "audio/ogg"
    if header.startswith(b"ID3") or (
        len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
    ):
        return "audio", "audio/mpeg"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand == b"qt  ":
            return "video", "video/quicktime"
        # M4A is an ISO-BMFF audio container; common audio brands start M4A.
        if brand.startswith(b"M4A"):
            return "audio", "audio/mp4"
        return "video", "video/mp4"
    if header.startswith(b"\x1aE\xdf\xa3"):
        suffix = Path(filename).suffix.lower()
        return ("audio", "audio/webm") if declared_type.startswith("audio/") else ("video", "video/webm")

    # Plain text has no magic number. Accept only explicit text intent, valid
    # UTF-8, and no NUL bytes; active formats such as SVG/HTML are not accepted.
    suffix = Path(filename).suffix.lower()
    if declared_type.startswith("text/plain") or suffix == ".txt":
        try:
            header.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            if b"\x00" not in header:
                return "text", "text/plain"
    raise MediaSecurityError("unsupported_media", "Unsupported or invalid media file.", 415)


def _validate_declared_type(declared: str, detected_media: str) -> None:
    declared = (declared or "").split(";", 1)[0].strip().lower()
    if not declared or declared == "application/octet-stream":
        return
    declared_media = declared.split("/", 1)[0]
    if declared_media != detected_media:
        raise MediaSecurityError(
            "media_type_mismatch",
            "The uploaded file content does not match its declared media type.",
            415,
        )


def _validate_extension(filename: str, detected_media: str) -> None:
    suffix = Path(filename).suffix.lower()
    allowed = _EXTENSIONS_BY_MEDIA[detected_media]
    if suffix and suffix not in allowed:
        raise MediaSecurityError(
            "file_extension_mismatch",
            "The uploaded file extension does not match its content.",
            415,
        )


async def stream_validated_upload(
    upload,
    *,
    max_bytes: int,
    allowed_media_types: Iterable[str] = ("image", "audio", "video", "text"),
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    temp_dir: str | None = None,
) -> ValidatedUpload:
    """Stream an async upload into a private temporary file with a hard limit.

    The temporary file is removed automatically on every validation/read error.
    On success its lifecycle belongs to the caller and must end in ``finally``.
    """
    if max_bytes <= 0 or chunk_size <= 0:
        raise ValueError("max_bytes and chunk_size must be positive")

    original = str(getattr(upload, "filename", "") or "upload")
    normalized = safe_filename(original, default="upload.bin")
    declared = str(getattr(upload, "content_type", "") or "")
    allowed = frozenset(allowed_media_types)
    unknown = allowed.difference(_EXTENSIONS_BY_MEDIA)
    if unknown:
        raise ValueError(f"Unknown allowed media types: {sorted(unknown)}")

    suffix = Path(normalized).suffix[:16]
    handle = tempfile.NamedTemporaryFile(
        mode="w+b",
        delete=False,
        suffix=suffix,
        prefix="media_",
        dir=temp_dir,
    )
    path = handle.name
    size = 0
    digest = hashlib.sha256()
    signature = bytearray()
    try:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            if not isinstance(chunk, (bytes, bytearray)):
                raise MediaSecurityError("invalid_upload", "Invalid upload stream.")
            size += len(chunk)
            if size > max_bytes:
                raise MediaSecurityError(
                    "file_too_large",
                    f"File exceeds the {max_bytes}-byte upload limit.",
                    413,
                )
            digest.update(chunk)
            if len(signature) < MAX_SIGNATURE_BYTES:
                signature.extend(chunk[: MAX_SIGNATURE_BYTES - len(signature)])
            handle.write(chunk)
        handle.flush()

        if size == 0:
            raise MediaSecurityError("empty_file", "The uploaded file is empty.")
        media_type, mime_type = detect_signature(
            bytes(signature), filename=normalized, declared_type=declared
        )
        if media_type not in allowed:
            raise MediaSecurityError(
                "media_type_not_allowed",
                "This media type is not allowed for the requested operation.",
                415,
            )
        _validate_declared_type(declared, media_type)
        _validate_extension(normalized, media_type)
        return ValidatedUpload(
            path=path,
            original_filename=original,
            filename=normalized,
            size=size,
            sha256=digest.hexdigest(),
            media_type=media_type,
            mime_type=mime_type,
        )
    except BaseException:
        handle.close()
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        if not handle.closed:
            handle.close()


def remove_temp_file(path: str | os.PathLike[str] | None) -> None:
    """Best-effort removal restricted to the OS temporary directory."""
    if not path:
        return
    candidate = Path(path).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        candidate.relative_to(temp_root)
    except ValueError:
        return
    try:
        candidate.unlink(missing_ok=True)
    except OSError:
        pass


class SlidingWindowRateLimiter:
    """Small process-local per-principal sliding-window limiter."""

    def __init__(self, limit: int, window_seconds: float):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, principal_id: str, *, now: float | None = None) -> bool:
        key = str(principal_id or "")
        if not key:
            return False
        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self.window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(timestamp)
            return True


class InMemoryQuota:
    """Atomic process-local byte reservation for concurrent uploads."""

    def __init__(self, max_bytes_per_principal: int):
        if max_bytes_per_principal <= 0:
            raise ValueError("max_bytes_per_principal must be positive")
        self.max_bytes = max_bytes_per_principal
        self._reserved: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def reserve(self, principal_id: str, byte_count: int) -> bool:
        if not principal_id or byte_count <= 0:
            return False
        async with self._lock:
            current = self._reserved[principal_id]
            if current + byte_count > self.max_bytes:
                return False
            self._reserved[principal_id] = current + byte_count
            return True

    async def release(self, principal_id: str, byte_count: int) -> None:
        if not principal_id or byte_count <= 0:
            return
        async with self._lock:
            remaining = max(0, self._reserved[principal_id] - byte_count)
            if remaining:
                self._reserved[principal_id] = remaining
            else:
                self._reserved.pop(principal_id, None)

    @asynccontextmanager
    async def reservation(self, principal_id: str, byte_count: int) -> AsyncIterator[None]:
        if not await self.reserve(principal_id, byte_count):
            raise MediaSecurityError("quota_exceeded", "Upload quota exceeded.", 413)
        try:
            yield
        finally:
            await self.release(principal_id, byte_count)


T = TypeVar("T")


class BoundedJobRunner:
    """Bound global job concurrency and cancel work after a fixed timeout."""

    def __init__(self, max_concurrency: int, timeout_seconds: float):
        if max_concurrency <= 0 or timeout_seconds <= 0:
            raise ValueError("max_concurrency and timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(self, awaitable: Awaitable[T]) -> T:
        async with self._semaphore:
            try:
                return await asyncio.wait_for(awaitable, timeout=self.timeout_seconds)
            except asyncio.TimeoutError as exc:
                raise MediaSecurityError(
                    "job_timeout",
                    "Media processing timed out. Please try again.",
                    504,
                ) from exc
