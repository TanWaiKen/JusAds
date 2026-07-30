import asyncio
from pathlib import Path

import pytest

from shared.media_security import (
    BoundedJobRunner,
    InMemoryQuota,
    MediaSecurityError,
    SlidingWindowRateLimiter,
    remove_temp_file,
    stream_validated_upload,
)
from shared.s3_client import build_s3_key, is_private_key_for_user, safe_filename


class FakeUpload:
    def __init__(self, data: bytes, filename: str, content_type: str):
        self.data = data
        self.filename = filename
        self.content_type = content_type
        self.offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self.data[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def test_private_key_is_opaque_and_filename_cannot_escape_prefix():
    key = build_s3_key(
        "upload",
        "developer@example.com",
        "project-id",
        "check-id",
        "../../voice sample?.mp3",
    )
    assert key.startswith("private/uploads/user-")
    assert "developer@example.com" not in key
    assert ".." not in key
    assert key.endswith("/voice_sample.mp3")
    assert is_private_key_for_user(key, "developer@example.com")
    assert not is_private_key_for_user(key, "other@example.com")


def test_safe_filename_normalizes_windows_and_control_characters():
    assert safe_filename("..\\folder\\\x00my ad.PNG") == "my_ad.PNG"


@pytest.mark.asyncio
async def test_streamed_png_is_validated_and_hashed(tmp_path):
    data = b"\x89PNG\r\n\x1a\n" + b"x" * 32
    upload = FakeUpload(data, "creative.png", "image/png")
    result = await stream_validated_upload(
        upload,
        max_bytes=1024,
        allowed_media_types={"image"},
        temp_dir=str(tmp_path),
    )
    try:
        assert result.size == len(data)
        assert result.media_type == "image"
        assert result.mime_type == "image/png"
        assert Path(result.path).read_bytes() == data
    finally:
        # A route owns successful files and removes them in its own finally.
        Path(result.path).unlink()


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected_and_partial_file_removed(tmp_path):
    upload = FakeUpload(b"\xff\xd8\xff" + b"x" * 30, "large.jpg", "image/jpeg")
    before = set(tmp_path.iterdir())
    with pytest.raises(MediaSecurityError) as error:
        await stream_validated_upload(upload, max_bytes=8, temp_dir=str(tmp_path))
    assert error.value.code == "file_too_large"
    assert set(tmp_path.iterdir()) == before


@pytest.mark.asyncio
async def test_spoofed_media_type_is_rejected_and_cleaned(tmp_path):
    upload = FakeUpload(b"\x89PNG\r\n\x1a\npayload", "fake.mp4", "video/mp4")
    with pytest.raises(MediaSecurityError) as error:
        await stream_validated_upload(upload, max_bytes=1024, temp_dir=str(tmp_path))
    assert error.value.code == "media_type_mismatch"
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_rate_quota_and_timeout_controls():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
    assert await limiter.allow("sub", now=1)
    assert await limiter.allow("sub", now=2)
    assert not await limiter.allow("sub", now=3)
    assert await limiter.allow("sub", now=12)

    quota = InMemoryQuota(max_bytes_per_principal=10)
    assert await quota.reserve("sub", 7)
    assert not await quota.reserve("sub", 4)
    await quota.release("sub", 7)
    assert await quota.reserve("sub", 10)

    runner = BoundedJobRunner(max_concurrency=1, timeout_seconds=0.01)
    with pytest.raises(MediaSecurityError) as error:
        await runner.run(asyncio.sleep(0.1))
    assert error.value.code == "job_timeout"
