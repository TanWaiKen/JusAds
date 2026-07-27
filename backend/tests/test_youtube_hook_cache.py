from jusads_trends.youtube_hook_cache import (
    build_hook_query,
    market_region_code,
    profile_fingerprint,
    serialise_video,
)


def test_company_context_changes_the_cache_fingerprint_and_query():
    coffee = {"company_name": "Bean Co", "product_category": "coffee", "product_description": "cold brew"}
    noodles = {"company_name": "Noodle Co", "product_category": "noodles", "product_description": "rice rolls"}

    assert profile_fingerprint(coffee, "malaysia") != profile_fingerprint(noodles, "malaysia")
    assert "coffee cold brew" in build_hook_query(coffee, "malaysia")
    assert market_region_code("malaysia") == "MY"
    assert market_region_code("unknown") == "MY"


def test_serialise_video_exposes_only_public_reference_fields():
    class Video:
        video_id = "abc123def45"
        title = "Hook example"
        channel_title = "Public channel"
        published_at = "2026-01-01T00:00:00Z"
        thumbnail_high_url = "https://img.example/video.jpg"
        thumbnail_url = ""
        watch_url = "https://www.youtube.com/watch?v=abc123def45"

    item = serialise_video(Video())
    assert item["video_id"] == "abc123def45"
    assert item["watch_url"].startswith("https://www.youtube.com/")
    assert set(item) == {"video_id", "title", "channel_title", "published_at", "thumbnail_url", "watch_url"}
