"""
fallback_queue.py
─────────────────
Manages local fallback storage and retry logic for S3/Supabase failures.

When S3 or Supabase is unavailable, operations are queued locally and retried
in the background. This ensures the core compliance check never fails due to
infrastructure issues.

Retry configurations:
  - Supabase writes: max 5 attempts, 60-second intervals
  - S3 uploads: max 3 attempts, 30-second intervals

After all retries are exhausted, the local fallback data is retained and a
CRITICAL-level alert is logged.

Requirements: 3.5, 4.5, 4.7, 7.1, 7.2, 7.5
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Directory for local fallback JSON files
FALLBACK_DIR = Path(__file__).resolve().parent.parent / "assets" / "fallback"


@dataclass
class SupabaseQueueItem:
    """A queued Supabase write operation."""

    check_id: str
    record: dict
    attempts: int = 0
    max_attempts: int = 5
    retry_interval: float = 60.0  # seconds
    last_attempt: float = 0.0


@dataclass
class S3QueueItem:
    """A queued S3 upload operation."""

    local_path: str
    s3_key: str
    attempts: int = 0
    max_attempts: int = 3
    retry_interval: float = 30.0  # seconds
    last_attempt: float = 0.0


class FallbackQueue:
    """Manages local fallback storage and retry logic for S3/Supabase failures.

    When external services are unavailable, this class:
    1. Stores data locally (JSON files for Supabase, retains local files for S3)
    2. Queues operations for background retry
    3. Processes the queue with configurable retry intervals and max attempts
    4. Logs CRITICAL alerts when all retries are exhausted

    Attributes:
        fallback_dir: Path to the local fallback storage directory.
        supabase_queue: List of pending Supabase write operations.
        s3_queue: List of pending S3 upload operations.
        _running: Flag indicating whether the background processor is active.
    """

    def __init__(
        self,
        fallback_dir: Optional[Path] = None,
        supabase_client=None,
        s3_client=None,
    ):
        """Initialize the FallbackQueue.

        Args:
            fallback_dir: Directory for storing fallback JSON files.
                Defaults to backend/assets/fallback/.
            supabase_client: Optional SupabaseComplianceStore instance for retries.
            s3_client: Optional S3MediaClient instance for retries.
        """
        self.fallback_dir = fallback_dir or FALLBACK_DIR
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

        self.supabase_client = supabase_client
        self.s3_client = s3_client

        self.supabase_queue: list[SupabaseQueueItem] = []
        self.s3_queue: list[S3QueueItem] = []
        self._running: bool = False

    def queue_supabase_write(self, check_id: str, record: dict) -> None:
        """Store record locally as a JSON file and queue for retry.

        The record is persisted to disk immediately at
        `backend/assets/fallback/{check_id}.json` so data is never lost,
        even if the process crashes before retries succeed.

        Args:
            check_id: Unique identifier for the compliance check.
            record: The compliance check record dict to persist.
        """
        # Persist to local fallback file
        fallback_path = self.fallback_dir / f"{check_id}.json"
        try:
            with open(fallback_path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, default=str)
            logger.warning(
                "Supabase unavailable — queued check %s for retry. "
                "Fallback stored at: %s",
                check_id,
                fallback_path,
            )
        except OSError as e:
            logger.error(
                "Failed to write fallback file for check %s: %s", check_id, e
            )

        # Add to in-memory retry queue
        item = SupabaseQueueItem(check_id=check_id, record=record)
        self.supabase_queue.append(item)

    def queue_s3_upload(self, local_path: str, s3_key: str) -> None:
        """Queue a failed S3 upload for retry.

        The local file is retained in place. The queue tracks the local path
        and target S3 key for background retry.

        Args:
            local_path: Path to the local file that failed to upload.
            s3_key: The target S3 object key.
        """
        logger.warning(
            "S3 upload failed — queued for retry: %s → %s", local_path, s3_key
        )
        item = S3QueueItem(local_path=local_path, s3_key=s3_key)
        self.s3_queue.append(item)

    async def process_queue(self) -> None:
        """Background task that retries queued operations.

        This method is designed to be run as a FastAPI background task.
        It loops continuously, checking each queued item and retrying
        when the retry interval has elapsed.

        Retry configurations:
          - Supabase: 5 attempts, 60-second intervals
          - S3: 3 attempts, 30-second intervals

        When all retries for an item are exhausted:
          - A CRITICAL-level message is logged
          - The local fallback data is retained (never deleted)
          - The item is removed from the in-memory queue

        The loop exits when both queues are empty.
        """
        self._running = True
        logger.info("Fallback queue processor started.")

        try:
            while self._running and (self.supabase_queue or self.s3_queue):
                await self._process_supabase_queue()
                await self._process_s3_queue()

                # Sleep before next check cycle to avoid busy-waiting.
                # Use the minimum retry interval from remaining items, capped
                # between 1s and 5s, so tests with interval=0 don't hang.
                if self.supabase_queue or self.s3_queue:
                    min_interval = self._min_remaining_interval()
                    sleep_time = max(1.0, min(min_interval, 5.0))
                    await asyncio.sleep(sleep_time)
        finally:
            self._running = False
            logger.info("Fallback queue processor stopped.")

    async def _process_supabase_queue(self) -> None:
        """Process pending Supabase write operations."""
        completed: list[int] = []

        for idx, item in enumerate(self.supabase_queue):
            now = time.time()

            # Check if retry interval has elapsed
            if now - item.last_attempt < item.retry_interval:
                continue

            item.attempts += 1
            item.last_attempt = now

            success = await self._retry_supabase_write(item)

            if success:
                logger.info(
                    "Supabase retry succeeded for check %s (attempt %d/%d)",
                    item.check_id,
                    item.attempts,
                    item.max_attempts,
                )
                # Remove fallback file on success
                self._remove_fallback_file(item.check_id)
                completed.append(idx)
            elif item.attempts >= item.max_attempts:
                logger.critical(
                    "ALERT: All %d Supabase retry attempts exhausted for check %s. "
                    "Local fallback data retained at: %s",
                    item.max_attempts,
                    item.check_id,
                    self.fallback_dir / f"{item.check_id}.json",
                )
                completed.append(idx)

        # Remove completed/exhausted items (iterate in reverse to preserve indices)
        for idx in sorted(completed, reverse=True):
            self.supabase_queue.pop(idx)

    async def _process_s3_queue(self) -> None:
        """Process pending S3 upload operations."""
        completed: list[int] = []

        for idx, item in enumerate(self.s3_queue):
            now = time.time()

            # Check if retry interval has elapsed
            if now - item.last_attempt < item.retry_interval:
                continue

            item.attempts += 1
            item.last_attempt = now

            success = await self._retry_s3_upload(item)

            if success:
                logger.info(
                    "S3 retry succeeded for %s → %s (attempt %d/%d)",
                    item.local_path,
                    item.s3_key,
                    item.attempts,
                    item.max_attempts,
                )
                completed.append(idx)
            elif item.attempts >= item.max_attempts:
                logger.critical(
                    "ALERT: All %d S3 retry attempts exhausted for upload %s → %s. "
                    "Local file retained at: %s",
                    item.max_attempts,
                    item.local_path,
                    item.s3_key,
                    item.local_path,
                )
                completed.append(idx)

        # Remove completed/exhausted items
        for idx in sorted(completed, reverse=True):
            self.s3_queue.pop(idx)

    async def _retry_supabase_write(self, item: SupabaseQueueItem) -> bool:
        """Attempt to write a queued record to Supabase.

        Args:
            item: The queued Supabase write operation.

        Returns:
            True if the write succeeded, False otherwise.
        """
        if self.supabase_client is None:
            logger.debug("No Supabase client configured — retry skipped.")
            return False

        try:
            # Check connectivity first
            if not self.supabase_client.health_check():
                logger.debug(
                    "Supabase still unreachable for check %s (attempt %d/%d)",
                    item.check_id,
                    item.attempts,
                    item.max_attempts,
                )
                return False

            # Attempt the write — construct CheckRecord from stored dict
            try:
                from agent.models import CheckRecord

                record = CheckRecord(**item.record)
            except Exception:
                # If model instantiation fails, pass the raw dict
                # (allows the client to handle it)
                record = item.record  # type: ignore[assignment]

            return self.supabase_client.insert_check(record)
        except Exception as e:
            logger.error(
                "Supabase retry failed for check %s (attempt %d/%d): %s",
                item.check_id,
                item.attempts,
                item.max_attempts,
                e,
            )
            return False

    async def _retry_s3_upload(self, item: S3QueueItem) -> bool:
        """Attempt to upload a queued file to S3.

        Args:
            item: The queued S3 upload operation.

        Returns:
            True if the upload succeeded, False otherwise.
        """
        if self.s3_client is None:
            logger.debug("No S3 client configured — retry skipped.")
            return False

        # Verify local file still exists
        if not os.path.exists(item.local_path):
            logger.error(
                "Local file no longer exists for S3 retry: %s", item.local_path
            )
            return False

        try:
            self.s3_client.upload_file(item.local_path, item.s3_key)
            return True
        except Exception as e:
            logger.error(
                "S3 retry failed for %s → %s (attempt %d/%d): %s",
                item.local_path,
                item.s3_key,
                item.attempts,
                item.max_attempts,
                e,
            )
            return False

    def _remove_fallback_file(self, check_id: str) -> None:
        """Remove a fallback JSON file after successful persistence.

        Args:
            check_id: The check_id whose fallback file should be removed.
        """
        fallback_path = self.fallback_dir / f"{check_id}.json"
        try:
            if fallback_path.exists():
                fallback_path.unlink()
                logger.debug("Removed fallback file: %s", fallback_path)
        except OSError as e:
            logger.warning("Failed to remove fallback file %s: %s", fallback_path, e)

    def stop(self) -> None:
        """Signal the background processor to stop."""
        self._running = False

    def _min_remaining_interval(self) -> float:
        """Calculate the minimum time until any queued item is ready to retry.

        Returns:
            Minimum seconds until the next retry is due, or 0 if any item
            is ready immediately.
        """
        now = time.time()
        min_wait = float("inf")

        for item in self.supabase_queue:
            elapsed = now - item.last_attempt
            remaining = max(0.0, item.retry_interval - elapsed)
            min_wait = min(min_wait, remaining)

        for item in self.s3_queue:
            elapsed = now - item.last_attempt
            remaining = max(0.0, item.retry_interval - elapsed)
            min_wait = min(min_wait, remaining)

        return min_wait if min_wait != float("inf") else 0.0

    @property
    def pending_count(self) -> int:
        """Total number of pending items across both queues."""
        return len(self.supabase_queue) + len(self.s3_queue)
