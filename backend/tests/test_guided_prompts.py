"""Tests for guided video hook assembly."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jusads_generation.guided_prompts import assemble_guided_message


def _video_inputs() -> dict[str, str]:
    return {
        "product_name": "Demo Brew Coffee",
        "key_message": "Freshly roasted coffee beans.",
        "call_to_action": "Learn More",
        "language": "English",
        "creative_mode": "voiceover",
        "platform": "tiktok",
    }


def test_guided_video_includes_selected_opening_hook() -> None:
    inputs = _video_inputs()
    inputs["opening_hook"] = "Sudden action → product reveal"

    message = assemble_guided_message("video_ad", inputs)

    assert "OPENING HOOK: Sudden action → product reveal" in message
    assert "Execute the user's selected OPENING HOOK" in message


def test_guided_video_remains_compatible_without_opening_hook() -> None:
    message = assemble_guided_message("video_ad", _video_inputs())

    assert "OPENING HOOK:" not in message
    assert "Generate a video ad." in message
