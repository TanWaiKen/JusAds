"""
youtube_client.py
─────────────────
Standalone YouTube Data API v3 client library.

A clean, self-contained wrapper around the YouTube Data API v3 using the
official ``google-api-python-client``. Designed for easy review and reuse.

Docs: https://developers.google.com/youtube/v3/docs

Usage::

    from shared.youtube_client import YouTubeClient

    client = YouTubeClient(api_key="YOUR_KEY")

    # Search for videos
    results = client.search_videos("funny ad transition meme", max_results=5)

    # Get video details
    details = client.get_video_details(["dQw4w9WgXcQ", "abc123"])

    # Search with filters
    results = client.search_videos(
        query="product reveal ad",
        duration="short",         # short (<4min) | medium (4-20min) | long (>20min)
        order="viewCount",        # relevance | date | rating | viewCount | title
        region_code="MY",         # ISO 3166-1 alpha-2 country code
        relevance_language="ms",  # ISO 639-1 language code
        published_after="2024-01-01T00:00:00Z",
    )

Prerequisites::

    pip install google-api-python-client

Environment:
    YOUTUBE_API_KEY — API key from Google Cloud Console
"""

import logging
from datetime import datetime
from typing import Any, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


# ─── Data Classes ─────────────────────────────────────────────────────────────


class VideoSearchResult:
    """A single video result from YouTube search."""

    def __init__(
        self,
        video_id: str,
        title: str,
        description: str,
        channel_title: str,
        channel_id: str,
        published_at: str,
        thumbnail_url: str,
        thumbnail_high_url: str = "",
    ):
        self.video_id = video_id
        self.title = title
        self.description = description
        self.channel_title = channel_title
        self.channel_id = channel_id
        self.published_at = published_at
        self.thumbnail_url = thumbnail_url
        self.thumbnail_high_url = thumbnail_high_url

    @property
    def watch_url(self) -> str:
        """Full YouTube watch URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def short_url(self) -> str:
        """Short youtu.be URL."""
        return f"https://youtu.be/{self.video_id}"

    @property
    def embed_url(self) -> str:
        """Embeddable URL for iframes."""
        return f"https://www.youtube.com/embed/{self.video_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON responses."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "description": self.description,
            "channel_title": self.channel_title,
            "channel_id": self.channel_id,
            "published_at": self.published_at,
            "thumbnail_url": self.thumbnail_url,
            "thumbnail_high_url": self.thumbnail_high_url,
            "watch_url": self.watch_url,
            "short_url": self.short_url,
            "embed_url": self.embed_url,
        }


class VideoDetails:
    """Full details for a specific video (from videos.list endpoint)."""

    def __init__(
        self,
        video_id: str,
        title: str,
        description: str,
        channel_title: str,
        published_at: str,
        duration: str,
        view_count: int,
        like_count: int,
        comment_count: int,
        tags: list[str],
        category_id: str,
        thumbnail_url: str,
        default_language: str = "",
        is_embeddable: bool = True,
    ):
        self.video_id = video_id
        self.title = title
        self.description = description
        self.channel_title = channel_title
        self.published_at = published_at
        self.duration = duration
        self.view_count = view_count
        self.like_count = like_count
        self.comment_count = comment_count
        self.tags = tags
        self.category_id = category_id
        self.thumbnail_url = thumbnail_url
        self.default_language = default_language
        self.is_embeddable = is_embeddable

    @property
    def watch_url(self) -> str:
        """Full YouTube watch URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON responses."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "description": self.description,
            "channel_title": self.channel_title,
            "published_at": self.published_at,
            "duration": self.duration,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "tags": self.tags,
            "category_id": self.category_id,
            "thumbnail_url": self.thumbnail_url,
            "default_language": self.default_language,
            "is_embeddable": self.is_embeddable,
            "watch_url": self.watch_url,
        }


# ─── Client ───────────────────────────────────────────────────────────────────


class YouTubeClient:
    """YouTube Data API v3 client.

    Wraps the official ``google-api-python-client`` discovery service with
    typed methods for common operations: search, video details, and channel
    info. Handles errors gracefully and logs all API interactions.

    Args:
        api_key: YouTube Data API v3 key from Google Cloud Console.
            If not provided, attempts to read from shared.config.
    """

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            from shared.config import YOUTUBE_API_KEY
            api_key = YOUTUBE_API_KEY

        if not api_key:
            logger.warning("[YouTube] No API key provided — client will be non-functional")

        self._api_key = api_key
        self._service = None

    @property
    def service(self):
        """Lazy-initialize the YouTube API service (avoids import-time network calls)."""
        if self._service is None:
            if not self._api_key:
                raise ValueError("YouTube API key is required but not configured")
            self._service = build(
                API_SERVICE_NAME,
                API_VERSION,
                developerKey=self._api_key,
                cache_discovery=False,
            )
        return self._service

    @property
    def is_configured(self) -> bool:
        """Check if the client has a valid API key."""
        return bool(self._api_key)

    # ─── Search ───────────────────────────────────────────────────────────────

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        duration: Optional[str] = None,
        order: str = "relevance",
        region_code: Optional[str] = None,
        relevance_language: Optional[str] = None,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        video_type: str = "any",
        safe_search: str = "moderate",
        video_embeddable: str = "true",
        page_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Search for videos using youtube.search.list.

        Docs: https://developers.google.com/youtube/v3/docs/search/list

        Args:
            query: Search query string.
            max_results: Maximum number of results (1–50).
            duration: Video length filter.
                - "short" → less than 4 minutes
                - "medium" → 4–20 minutes
                - "long" → more than 20 minutes
                - None → any duration
            order: Sort order.
                - "relevance" (default)
                - "date" (newest first)
                - "rating" (highest rated)
                - "viewCount" (most viewed)
                - "title" (alphabetical)
            region_code: ISO 3166-1 alpha-2 country code (e.g. "MY", "SG").
                Restricts results to videos available in that country.
            relevance_language: ISO 639-1 language code (e.g. "ms", "zh").
                Biases results toward videos with metadata in that language.
            published_after: RFC 3339 timestamp (e.g. "2024-01-01T00:00:00Z").
                Only return videos published after this date.
            published_before: RFC 3339 timestamp. Only return videos before this date.
            video_type: "any" | "episode" | "movie".
            safe_search: "moderate" | "none" | "strict".
            video_embeddable: "true" | "any". Filter to embeddable videos only.
            page_token: Token for pagination (from previous response's nextPageToken).

        Returns:
            Dict with:
                - "results": list[VideoSearchResult]
                - "total_results": int (estimated total)
                - "next_page_token": str | None
                - "prev_page_token": str | None

        Raises:
            ValueError: If API key is not configured.
            HttpError: If the YouTube API returns an error response.
        """
        params: dict[str, Any] = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(max(1, max_results), 50),
            "order": order,
            "safeSearch": safe_search,
            "videoEmbeddable": video_embeddable,
        }

        if duration:
            params["videoDuration"] = duration
        if region_code:
            params["regionCode"] = region_code
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        if published_after:
            params["publishedAfter"] = published_after
        if published_before:
            params["publishedBefore"] = published_before
        if video_type != "any":
            params["videoType"] = video_type
        if page_token:
            params["pageToken"] = page_token

        logger.info("[YouTube] search.list: q=%s, maxResults=%d", query[:60], params["maxResults"])

        try:
            request = self.service.search().list(**params)
            response = request.execute()
        except HttpError as e:
            logger.error("[YouTube] search.list failed: %s", e)
            raise

        # Parse results
        results: list[VideoSearchResult] = []
        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue

            snippet = item.get("snippet", {})
            thumbnails = snippet.get("thumbnails", {})

            results.append(VideoSearchResult(
                video_id=video_id,
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                channel_title=snippet.get("channelTitle", ""),
                channel_id=snippet.get("channelId", ""),
                published_at=snippet.get("publishedAt", ""),
                thumbnail_url=thumbnails.get("medium", {}).get("url", ""),
                thumbnail_high_url=thumbnails.get("high", {}).get("url", ""),
            ))

        page_info = response.get("pageInfo", {})
        return {
            "results": results,
            "total_results": page_info.get("totalResults", 0),
            "next_page_token": response.get("nextPageToken"),
            "prev_page_token": response.get("prevPageToken"),
        }

    # ─── Video Details ────────────────────────────────────────────────────────

    def get_video_details(
        self,
        video_ids: list[str],
    ) -> list[VideoDetails]:
        """Get full details for specific video IDs using youtube.videos.list.

        Docs: https://developers.google.com/youtube/v3/docs/videos/list

        Args:
            video_ids: List of YouTube video IDs (max 50 per call).

        Returns:
            List of VideoDetails objects.

        Raises:
            ValueError: If API key is not configured.
            HttpError: If the YouTube API returns an error response.
        """
        if not video_ids:
            return []

        # API allows max 50 IDs per request
        ids_batch = video_ids[:50]

        logger.info("[YouTube] videos.list: %d video(s)", len(ids_batch))

        try:
            request = self.service.videos().list(
                part="snippet,contentDetails,statistics,status",
                id=",".join(ids_batch),
            )
            response = request.execute()
        except HttpError as e:
            logger.error("[YouTube] videos.list failed: %s", e)
            raise

        details: list[VideoDetails] = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            stats = item.get("statistics", {})
            status = item.get("status", {})
            thumbnails = snippet.get("thumbnails", {})

            details.append(VideoDetails(
                video_id=item.get("id", ""),
                title=snippet.get("title", ""),
                description=snippet.get("description", "")[:500],
                channel_title=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
                duration=content.get("duration", ""),
                view_count=int(stats.get("viewCount", 0)),
                like_count=int(stats.get("likeCount", 0)),
                comment_count=int(stats.get("commentCount", 0)),
                tags=snippet.get("tags", [])[:20],
                category_id=snippet.get("categoryId", ""),
                thumbnail_url=thumbnails.get("high", {}).get("url", ""),
                default_language=snippet.get("defaultLanguage", ""),
                is_embeddable=status.get("embeddable", True),
            ))

        return details

    # ─── Search Shortcuts ─────────────────────────────────────────────────────

    def search_shorts(
        self,
        query: str,
        max_results: int = 10,
        region_code: Optional[str] = None,
        order: str = "relevance",
        strict_duration: bool = True,
    ) -> list[VideoSearchResult]:
        """Search for YouTube Shorts only (≤60 seconds).

        YouTube API doesn't have a native Shorts filter, so this method:
        1. Appends "#shorts" to the query to bias toward Shorts content
        2. Sets videoDuration="short" (API filter: <4 minutes)
        3. Optionally post-filters via videos.list to keep only ≤60s videos

        Args:
            query: Search terms (do NOT include #shorts — added automatically).
            max_results: Number of results to return.
            region_code: Country code for regional results.
            order: Sort order (relevance, date, viewCount, rating).
            strict_duration: If True, fetches video details and removes
                anything over 60 seconds. Costs an extra API call but
                guarantees only Shorts are returned.

        Returns:
            List of VideoSearchResult objects (only Shorts).
        """
        # Append #shorts to bias YouTube's search toward Shorts content
        shorts_query = f"{query} #shorts"

        # Over-fetch to account for post-filtering
        fetch_count = max_results * 2 if strict_duration else max_results

        result = self.search_videos(
            query=shorts_query,
            max_results=min(fetch_count, 50),
            duration="short",
            region_code=region_code,
            order=order,
        )
        candidates = result["results"]

        if not strict_duration or not candidates:
            return candidates[:max_results]

        # Post-filter: get actual durations and keep only ≤60s
        video_ids = [v.video_id for v in candidates]
        try:
            details = self.get_video_details(video_ids)
        except Exception as exc:
            logger.warning("[YouTube] Shorts duration filter failed, returning unfiltered: %s", exc)
            return candidates[:max_results]

        # Parse ISO 8601 durations (PT15S, PT1M2S, etc.) and filter ≤60s
        short_ids: set[str] = set()
        for detail in details:
            seconds = _parse_iso_duration(detail.duration)
            if seconds <= 60:
                short_ids.add(detail.video_id)

        filtered = [v for v in candidates if v.video_id in short_ids]
        logger.info(
            "[YouTube] Shorts filter: %d candidates → %d actual Shorts (≤60s)",
            len(candidates), len(filtered),
        )
        return filtered[:max_results]

    def search_short_videos(
        self,
        query: str,
        max_results: int = 10,
        region_code: Optional[str] = None,
        order: str = "relevance",
    ) -> list[VideoSearchResult]:
        """Convenience: search for short videos only (<4 minutes).

        Note: For Shorts specifically (≤60s), use ``search_shorts()`` instead.
        This returns any video under 4 minutes.
        """
        result = self.search_videos(
            query=query,
            max_results=max_results,
            duration="short",
            region_code=region_code,
            order=order,
        )
        return result["results"]

    def search_trending(
        self,
        region_code: str = "MY",
        max_results: int = 10,
        category_id: str = "",
    ) -> list[VideoDetails]:
        """Get trending/popular videos for a region using videos.list chart=mostPopular.

        Docs: https://developers.google.com/youtube/v3/docs/videos/list
        (chart parameter)

        Args:
            region_code: ISO 3166-1 alpha-2 country code.
            max_results: Number of results (1–50).
            category_id: Optional video category ID to filter trending by category.

        Returns:
            List of VideoDetails for trending videos.
        """
        logger.info("[YouTube] videos.list chart=mostPopular: region=%s", region_code)

        params: dict[str, Any] = {
            "part": "snippet,contentDetails,statistics",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": min(max(1, max_results), 50),
        }
        if category_id:
            params["videoCategoryId"] = category_id

        try:
            request = self.service.videos().list(**params)
            response = request.execute()
        except HttpError as e:
            logger.error("[YouTube] trending videos.list failed: %s", e)
            raise

        details: list[VideoDetails] = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            stats = item.get("statistics", {})
            thumbnails = snippet.get("thumbnails", {})

            details.append(VideoDetails(
                video_id=item.get("id", ""),
                title=snippet.get("title", ""),
                description=snippet.get("description", "")[:500],
                channel_title=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
                duration=content.get("duration", ""),
                view_count=int(stats.get("viewCount", 0)),
                like_count=int(stats.get("likeCount", 0)),
                comment_count=int(stats.get("commentCount", 0)),
                tags=snippet.get("tags", [])[:20],
                category_id=snippet.get("categoryId", ""),
                thumbnail_url=thumbnails.get("high", {}).get("url", ""),
                default_language=snippet.get("defaultLanguage", ""),
            ))

        return details

    def search_by_channel(
        self,
        channel_id: str,
        query: str = "",
        max_results: int = 10,
        order: str = "date",
    ) -> list[VideoSearchResult]:
        """Search videos within a specific channel.

        Useful for finding hook-style content from known viral creators.

        Args:
            channel_id: YouTube channel ID.
            query: Optional search terms within the channel.
            max_results: Number of results.
            order: Sort order (default: newest first).

        Returns:
            List of VideoSearchResult from that channel.
        """
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "channelId": channel_id,
            "maxResults": min(max(1, max_results), 50),
            "order": order,
        }
        if query:
            params["q"] = query

        logger.info("[YouTube] search.list (channel): channel=%s, q=%s", channel_id[:12], query[:30])

        try:
            request = self.service.search().list(**params)
            response = request.execute()
        except HttpError as e:
            logger.error("[YouTube] channel search failed: %s", e)
            raise

        results: list[VideoSearchResult] = []
        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            thumbnails = snippet.get("thumbnails", {})
            results.append(VideoSearchResult(
                video_id=video_id,
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                channel_title=snippet.get("channelTitle", ""),
                channel_id=snippet.get("channelId", ""),
                published_at=snippet.get("publishedAt", ""),
                thumbnail_url=thumbnails.get("medium", {}).get("url", ""),
                thumbnail_high_url=thumbnails.get("high", {}).get("url", ""),
            ))

        return results


# ─── Module-Level Singleton ───────────────────────────────────────────────────


def _parse_iso_duration(duration: str) -> int:
    """Parse an ISO 8601 duration string (e.g. PT1M30S, PT15S, PT2H1M) to seconds.

    YouTube returns durations in this format from contentDetails.duration.
    Returns 0 on parse failure (treated as unknown — excluded by Shorts filter).
    """
    if not duration or not duration.startswith("PT"):
        return 0

    import re
    hours = re.search(r"(\d+)H", duration)
    minutes = re.search(r"(\d+)M", duration)
    seconds = re.search(r"(\d+)S", duration)

    total = 0
    if hours:
        total += int(hours.group(1)) * 3600
    if minutes:
        total += int(minutes.group(1)) * 60
    if seconds:
        total += int(seconds.group(1))
    return total


# Lazy singleton — instantiated on first use. Import and call directly:
#   from shared.youtube_client import youtube
#   results = youtube.search_shorts("meme transition ad")

_instance: Optional[YouTubeClient] = None


def get_client() -> YouTubeClient:
    """Get or create the module-level YouTubeClient singleton."""
    global _instance
    if _instance is None:
        _instance = YouTubeClient()
    return _instance


# Convenience alias
youtube = property(lambda self: get_client())
