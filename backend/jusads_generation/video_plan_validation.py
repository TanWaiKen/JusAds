"""Pure validation helpers for video storyboard production gates."""

from __future__ import annotations


def is_usable_v3_plan(plan: object) -> bool:
    """Return True only when a V3 plan has every visual needed for rendering."""
    if not isinstance(plan, dict):
        return False
    if plan.get("pipeline_version") != "v3_grid":
        return False

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return False

    frame_urls = plan.get("frame_urls") or plan.get("_frame_urls") or []
    grid_url = plan.get("grid_url") or plan.get("_grid_url") or ""
    usable_frames = [
        url for url in frame_urls
        if isinstance(url, str) and url.strip()
    ] if isinstance(frame_urls, list) else []

    return bool(grid_url) and len(usable_frames) >= len(scenes)
